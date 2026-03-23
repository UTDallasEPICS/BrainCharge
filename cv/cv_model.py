import torch.nn as nn
from torchvision.models import resnet50, ResNet50_Weights

def get_resnet():
    """Initialize the model"""
    modified_resnet = resnet50(weights=ResNet50_Weights.DEFAULT)
    # Modify the linear head
    modified_resnet.fc = nn.Sequential(
        nn.Linear(modified_resnet.fc.in_features, 4096, bias=True),
        nn.ReLU(inplace=True),
        nn.Dropout(),
        nn.Linear(4096, 1024, bias=True),
        nn.ReLU(inplace=True),
        nn.Dropout(),
        nn.Linear(1024, 7, bias=True)
    )

    # Freeze every layer of the model except linear head and last convolutions
    trainable_layers = ["fc", "layer4", "layer3.3", "layer3.2"]
    for name, param in modified_resnet.named_parameters():
        trainable = False
        for trainable_layer in trainable_layers:
            if trainable_layer in name:
                trainable = True
                break

        param.requires_grad = trainable

    return modified_resnet


def turn_off_batchnorm(model):
    """Turn off the BatchNorm for the data"""
    for module in model.modules():
        if isinstance(module, nn.BatchNorm2d):
            module.eval()
            for param in module.parameters():
                param.requires_grad = False