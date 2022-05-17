import torch
from config import parse_configs
from emotion_embedding_network import EmotionEmbeddingNetwork
from tensorboardX import SummaryWriter
from tqdm import tqdm
import torch.utils.data as tud
from dataset import IEMOCAPDataset
from dataset import EmotionEmbeddingNetworkCollate
from dataset import TacotronCollate
import numpy as np

def load(model, optimizer, path):
    checkpoint = torch.load(path)
    model.load_state_dict(checkpoint['state_dict'])
    optimizer.load_state_dict(checkpoint['optimizer'])


def train(configs):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print("CUDA", torch.cuda.is_available())
    if device.type == "cpu":
        configs.batch_size = 1

    emonet_train_data = IEMOCAPDataset(path_to_csv="data/splits/train.csv", silence=False, padded=True)
    emonet_val_data = IEMOCAPDataset(path_to_csv="data/splits/val.csv", silence=False, padded=True)

    emonet_collate_fn = EmotionEmbeddingNetworkCollate()
    emonet_train_loader = tud.DataLoader(train_data, collate_fn=collate_fn, num_workers=2, prefetch_factor=2, batch_size=4, shuffle=False)
    val_loader = tud.DataLoader(val_data, collate_fn=collate_fn, num_workers=2, prefetch_factor=2, batch_size=4, shuffle=False)

    weights = torch.from_numpy(np.load("data/weights.npy")).to(device)
    model = EmotionEmbeddingNetwork().to(device).to(torch.double)
    loss = torch.nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.Adam(model.parameters(), lr=configs.lr, weight_decay=.001)

    if configs.checkpoint:
        load(model, optimizer, configs.checkpoint)

    train_log_dir = 'logs/tensorboard/' + configs.name
    train_summary_writer = SummaryWriter(train_log_dir)
    epochs = configs.num_epochs
    update_step = 0

    running_loss = 0.0
    for e in tqdm(range(epochs)):
        for padded_melspec, emotions, padded_transcription, speakers, melspec_lens, transcription_lens in tqdm(train_loader, leave=False):
            melspecs = padded_melspec.to(device).to(torch.double)
            emotions = padded_melspec.to(device).to(torch.int64)
            model.train()
            y_pred, emotion_embedding = model(melspecs)
            J = loss(y_pred, emotions)
            optimizer.zero_grad()
            J.backward()
            optimizer.step()
            running_loss += J.item()
            if update_step % configs.train_loss_fr == 0:
                running_loss /= configs.train_loss_fr
                train_summary_writer.add_scalar(f'info/Training loss', running_loss, update_step)
                running_loss = 0.0
            if update_step % configs.val_loss_fr == 0:
                val_loss = 0.0
                model.eval()
                with torch.no_grad():
                    for melspecs, emotions, _ in tqdm(val_loader, leave=False):
                        melspecs = melspecs.to(device).to(torch.double)
                        emotions = emotions.to(device).to(torch.int64)
                        y_pred = model(melspecs)[0]
                        J = loss(y_pred, emotions)
                        val_loss += J.item()
                train_summary_writer.add_scalar(f'info/Validation loss', val_loss, update_step)
            update_step += 1

        state = {'state_dict': model.state_dict(),
                 'optimizer': optimizer.state_dict()}
        torch.save(state, "saved_models/" + configs.name + "_" + str(e) +"_.tar")

if __name__ == '__main__':
    configs = parse_configs()
    train(configs)

