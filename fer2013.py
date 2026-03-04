import torch
from torch.utils.data import Dataset
from torchvision.transforms import v2
from pathlib import Path
import random
from PIL import Image

TRAIN_VAL_SPLIT_RATE = 0.90 # 90/10 train val split

class FER2013(Dataset):
    def __init__(self, set_type: str="train"):
        if set_type not in ["train", "val", "test"]:
            raise ValueError("Invalid dataset type.")

        self.data = []
        self.emotion_to_idx = {}

        if set_type == "train":
            # For train set, the data will be augmented to endhance quality of model
            self.transform = v2.Compose([
                v2.RandomHorizontalFlip(),
                v2.RandomAffine(20, [0.1, 0.1], fill=128),
                v2.RandomResizedCrop(size=224, scale=(0.8, 1), ratio=(1.0, 1.0)),
                v2.ToImage(),
                v2.ToDtype(torch.float32, scale=True),
                v2.Normalize(
                    # Mean and stdev used for ImageNet
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225]
                )
            ])
        else:
            self.transform = v2.Compose([
                v2.Resize(224),
                v2.ToImage(),
                v2.ToDtype(torch.float32, scale=True),
                v2.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225]
                )
            ])

        root = Path("/content/emotions/train") if set_type != "test" else Path("/content/emotions/test")
        for idx, class_dir in enumerate(root.glob("*")):
            # Last element of the filepath
            label = class_dir.name
            for filename in class_dir.glob("*"):
                self.data.append([str(filename), label])
            self.emotion_to_idx[label] = idx

        if set_type != "test":
            random.seed(42) # To make training re-producible
            random.shuffle(self.data)
            split = int(len(self.data) * TRAIN_VAL_SPLIT_RATE)
            self.data = self.data[:split] if set_type == "train" else self.data[split:]


    def __len__(self):
        return len(self.data)


    def __getitem__(self, index):
        filename, label = self.data[index]
        img = Image.open(filename).convert("RGB")
        processed_img = self.transform(img)
        return processed_img, self.emotion_to_idx[label]