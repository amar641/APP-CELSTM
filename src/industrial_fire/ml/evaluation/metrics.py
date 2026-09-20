"""Evaluation metrics shared by training (validation loop) and offline model evaluation. See docs/ml/evaluation.md."""

from __future__ import annotations

import torch
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from torch import nn
from torch.utils.data import DataLoader


@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> dict:
    model.eval()
    criterion = nn.CrossEntropyLoss()
    total_loss = 0.0
    all_preds: list[int] = []
    all_labels: list[int] = []

    for decisions, intensities, availability, vision, vision_available, labels in loader:
        decisions, intensities, availability = decisions.to(device), intensities.to(device), availability.to(device)
        vision, vision_available, labels = vision.to(device), vision_available.to(device), labels.to(device)

        logits, _diagnostics = model(decisions, intensities, availability, vision, vision_available)
        total_loss += criterion(logits, labels).item() * labels.size(0)
        all_preds.extend(logits.argmax(dim=1).cpu().tolist())
        all_labels.extend(labels.cpu().tolist())

    n = max(len(all_labels), 1)
    return {
        "loss": total_loss / n,
        "accuracy": accuracy_score(all_labels, all_preds),
        "precision_macro": precision_score(all_labels, all_preds, average="macro", zero_division=0),
        "recall_macro": recall_score(all_labels, all_preds, average="macro", zero_division=0),
        "f1_macro": f1_score(all_labels, all_preds, average="macro", zero_division=0),
        "confusion_matrix": confusion_matrix(all_labels, all_preds).tolist(),
    }


def evaluate_sklearn(y_true: list[int], y_pred: list[int]) -> dict:
    """Same metric set as `evaluate`, for non-PyTorch (sklearn-API) classifiers like XGBoost."""
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision_macro": precision_score(y_true, y_pred, average="macro", zero_division=0),
        "recall_macro": recall_score(y_true, y_pred, average="macro", zero_division=0),
        "f1_macro": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
    }
