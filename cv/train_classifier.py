import torch
from torch.utils.data import DataLoader
import torch.optim as optim
from torch.optim import lr_scheduler
from torch import nn

from cv.cv_model import get_resnet, turn_off_batchnorm
from cv.fer2013 import FER2013

@torch.no_grad()
def get_acc(model, data_loader, arg_device) -> float:
    model.eval()

    correct, total = 0, 0
    for imgs, labels in data_loader:
        imgs, labels = imgs.to(arg_device), labels.to(arg_device)
        outputs = model(imgs)

        _, pred_labels = torch.max(outputs, dim=1)

        total += labels.shape[0]
        correct += int((pred_labels == labels).sum())

    return (correct / total) * 100


def save_model(arg_model, optimizer, scheduler):
    torch.save({
        "model": arg_model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "scheduler": scheduler.state_dict()
    },
    './emotion_model.pth')


def load_model(arg_model, optimizer, scheduler, device):
    """Load the model from the parameters"""
    checkpoint = torch.load('./emotion_model_checkpoint.pth', map_location=device)
    arg_model.load_state_dict(checkpoint["model"])
    if optimizer or scheduler:
        optimizer.load_state_dict(checkpoint["optimizer"])
        scheduler.load_state_dict(checkpoint["scheduler"])


def train(num_epochs, arg_model, train_dataloader, val_dataloader, loss_fn, optimizer, scheduler, device):
    for epoch in range(num_epochs):
        avg_train_loss, avg_val_loss = 0.0, 0.0

        arg_model.train()
        turn_off_batchnorm(arg_model)

        for imgs, labels in train_dataloader:
            imgs, labels = imgs.to(device), labels.to(device)
            optimizer.zero_grad()

            outputs = arg_model(imgs)
            train_loss = loss_fn(outputs, labels)
            train_loss.backward()
            optimizer.step()

            avg_train_loss += train_loss.item()

        avg_train_loss /= len(train_dataloader)
        train_acc = get_acc(arg_model, train_dataloader, device)

        arg_model.eval()
        with torch.no_grad():
            for imgs, labels in val_dataloader:
                imgs, labels = imgs.to(device), labels.to(device)
                optimizer.zero_grad()

                outputs = arg_model(imgs)
                val_loss = loss_fn(outputs, labels)

                avg_val_loss += val_loss.item()

            avg_val_loss /= len(val_dataloader)
            val_acc = get_acc(arg_model, val_dataloader, device)

        # Scheduling the learning rate after one epoch of training
        scheduler.step()

        print(f"Epoch {epoch + 1}/{num_epochs},")
        print(f"Train loss: {avg_train_loss:.4f}, val loss: {avg_val_loss:.4f}")
        print(f"Train acc: {train_acc:.4f}, val acc: {val_acc:.4f}")

def main():
    # Comment this out if you want to empty the cache
    torch.cuda.empty_cache()
    device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")

    resnet = get_resnet().to(device)
    optimizer = optim.SGD(
        resnet.parameters(), lr=1e-2, momentum=0.9, weight_decay=1e-4
    )
    scheduler = lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=60, eta_min=1e-5
    )

    # Data loader
    train_fer2013 = FER2013(set_type="train")
    val_fer2013 = FER2013(set_type="val")

    train_dataloader = DataLoader(
        train_fer2013, batch_size=128, shuffle=True, num_workers=2
    )
    val_dataloader = DataLoader(
        val_fer2013, batch_size=128, shuffle=False, num_workers=2
    )

    NUM_EPOCHS = 60

    load_model(resnet, optimizer, scheduler)
    train(
        num_epochs=NUM_EPOCHS,
        arg_model=resnet,
        train_dataloader=train_dataloader,
        val_dataloader=val_dataloader,
        loss_fn=nn.CrossEntropyLoss(label_smoothing=0.1),
        optimizer=optimizer,
        scheduler=scheduler
    )
    save_model(resnet, optimizer, scheduler)

if __name__ == "__main__":
    # Train or finetune the model
    main()