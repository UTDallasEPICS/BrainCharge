import torch.nn as nn
from torchvision.models import efficientnet_b2, EfficientNet_B2_Weights

def get_efficientnet(pretrained: bool=False):
    """Initialize the model"""
    efficientnet = (
        efficientnet_b2(weights=EfficientNet_B2_Weights.DEFAULT)
        if pretrained else
        efficientnet_b2()
    )
    # Modify the linear head
    efficientnet.classifier = nn.Sequential(
        nn.Linear(1408, 512, bias=True),
        nn.ReLU(inplace=True),
        nn.Dropout(),
        nn.Linear(512, 5, bias=True)
    )

    return efficientnet


def turn_off_batchnorm(model):
    """Turn off the BatchNorm for the data"""
    for module in model.modules():
        if isinstance(module, nn.BatchNorm2d):
            module.eval()
            for param in module.parameters():
                param.requires_grad = False