import torch
from torch.utils.data import Dataset
from torchvision.transforms import v2
from pathlib import Path
import random
from PIL import Image

TRAIN_VAL_SPLIT_RATE = 0.85 # 85, 15 train val split

class FER2013(Dataset):
    def __init__(self, set_type: str="train"):
        if set_type not in ["train", "val", "test"]:
            raise ValueError("Invalid dataset type.")

        self.data = []
        self.emotion_to_idx = {}

        if set_type == "train":
            # For train set, the data will be augmented to endhance quality of model
            self.transform = v2.Compose([
                v2.Lambda(lambda x: x.convert("L").convert("RGB")),
                v2.Resize([288, 288]),
                v2.RandomHorizontalFlip(),
                v2.RandomRotation(20),
                v2.ColorJitter(brightness=0.2, contrast=0.2),
                v2.ToImage(),
                v2.ToDtype(torch.float32, scale=True),
                v2.Normalize(mean=[0.485, 0.456, 0.406],
                            std=[0.229, 0.224, 0.225])
            ])
        else:
            self.transform = v2.Compose([
                v2.Lambda(lambda x: x.convert("L").convert("RGB")),
                v2.Resize([288, 288]),
                v2.ToImage(),
                v2.ToDtype(torch.float32, scale=True),
                v2.Normalize(mean=[0.485, 0.456, 0.406],
                            std=[0.229, 0.224, 0.225])
            ])

        if set_type != "test":
            root = Path("/content/emotions/train")
        else:
            root = Path("/content/emotions/test")

        classes = sorted([
            d.name for d in root.glob("*")
            if d.name not in ["disgust", "surprise"]
        ])

        self.emotion_to_idx = {cls: i for i, cls in enumerate(classes)}

        for cls in classes:
            class_dir = root / cls
            for filename in class_dir.glob("*"):
                self.data.append([str(filename), cls])

        if set_type != "test":
            random.shuffle(self.data)
            split = int(len(self.data) * TRAIN_VAL_SPLIT_RATE)

            if set_type == "train":
                self.data = self.data[:split]
            else:
                self.data = self.data[split:]


    def __len__(self):
        return len(self.data)


    def __getitem__(self, index):
        filename, label = self.data[index]
        img = Image.open(filename).convert("RGB")
        processed_img = self.transform(img)
        return processed_img, self.emotion_to_idx[label]