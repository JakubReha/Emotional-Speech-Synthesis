import torch
import csv
from torchvision import datasets  # type: ignore
import torchvision.transforms as T  # type: ignore
import torch.utils.data as tud
import matplotlib.pyplot as plt  # type: ignore
from torchvision.utils import make_grid  # type: ignore
import librosa.display
import torch.nn.functional as F
import sys
sys.path.append('tacotron2/')
from data_utils import TextMelLoader, TextMelCollate
from text import text_to_sequence
from text import sequence_to_text

class IEMOCAPDataset(torch.utils.data.Dataset):
    def __init__(self, path_to_csv: str, silence: bool, padded: bool):
        folder_name = "melspec"
        if padded:
            folder_name = f"padded_{folder_name}"
        if not silence:
            folder_name = f"{folder_name}_no_silence"
        self.silence = silence
        self.path_to_melspec = path_to_csv.split(sep=".")[:-1][0]
        self.path_to_melspec = self.path_to_melspec.replace('splits', folder_name)
        self.melspec_paths = []
        self.emotions = []
        self.speakers = []
        self.transcriptions = []

        with open(path_to_csv) as f:
            csv_reader = csv.reader(f, delimiter="|")
            next(csv_reader, None)
            count = 0
            for row in csv_reader:
                melspec_file = row[0].split(sep="/")[-1]
                if not self.silence:
                    melspec_file = f"{melspec_file.split('.')[0]}_no_silence_16k.pt"
                else:
                    melspec_file = f"{melspec_file.split('.')[0]}.pt"
                melspec_file = f"{self.path_to_melspec}/{melspec_file}"
                emotion = row[1]
                speaker = row[-1]
                transcription = row[5]
                self.melspec_paths += [melspec_file]
                self.emotions += [emotion]
                self.speakers += [speaker]
                self.transcriptions += [torch.IntTensor(text_to_sequence(text=transcription, cleaner_names=['english_cleaners']))]
                count += 1

    def __getitem__(self, index):
        return torch.load(self.melspec_paths[index]), int(self.emotions[index]), self.transcriptions[index], int(self.speakers[index])
    
    def __len__(self):
        return len(self.melspec_paths)

class EmotionEmbeddingNetworkCollate():
    def __call__(self, batch_data):
        melspecs = torch.zeros((len(batch_data), batch_data[0][0].shape[0], batch_data[0][0].shape[1]))
        emotions = torch.zeros((len(batch_data)))
        speakers = torch.zeros((len(batch_data)))
        for index, (melspec, emotion, transcription, speaker) in enumerate(batch_data):
            melspecs[index] = melspec
            emotions[index] = emotion
            speakers[index] = speaker
        return melspecs, emotions, speakers 

class TacotronCollate():
    def __call__(self, batch_data):
        melspec_lens = torch.LongTensor([melspec.shape[1] for melspec, _, _ in batch_data])
        transcription_lens = torch.LongTensor([len(transcription) for _, _, transcription in batch_data])
        max_melspec_len = torch.max(melspec_lens)
        max_transcription_len = torch.max(transcription_lens)

        padded_melspec = torch.zeros((len(batch_data), batch_data[0][0].shape[0], max_melspec_len))
        emotions = torch.zeros((len(batch_data)), dtype=torch.int)
        speakers = torch.zeros((len(batch_data)), dtype=torch.int)
        padded_transcription = torch.zeros((len(batch_data), max_transcription_len), dtype=torch.int)
        for index, (melspec, emotion, transcription, speaker) in enumerate(batch_data):
            melspec = F.pad(input=melspec, pad=(0, max_melspec_len - melspec.shape[1]), mode="constant", value=0.0)
            transcription = F.pad(input=transcription, pad=(0, max_transcription_len - len(transcription)), mode="constant", value=0)
            padded_melspec[index] = melspec
            padded_transcription[index] = transcription
            emotions[index] = emotion
            speakers[index] = speaker

        return padded_melspec, emotions, padded_transcription, speakers, melspec_lens, transcription_lens


def show_batch(dataloader):
    for text_padded, input_lengths, mel_padded, gate_padded, \
            output_lengths, emotions, speakers in dataloader:
        fig, axes = plt.subplots(nrows=len(emotions), figsize=(15, 10))
        for i in range(len(axes)):
            melspec = mel_padded[i][:, :]
            transcription = text_padded[i][:]
            axes[i].set_title(sequence_to_text(transcription.tolist()))
            img = librosa.display.specshow(melspec.numpy(), ax=axes[i])
            fig.colorbar(img, ax=axes[i])
        plt.show()
        break



if __name__ == "__main__":
    val_data = IEMOCAPDataset(path_to_csv="data/splits/val.csv", silence=False, padded=False)
    collate_fn = TextMelCollate(1)
    train_dataloader = tud.DataLoader(val_data, collate_fn=collate_fn, num_workers=2, prefetch_factor=2, batch_size=4, shuffle=False)
    show_batch(train_dataloader)