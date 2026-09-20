from uuid import uuid4

from industrial_fire.core.types import ClassificationLabel, ModelSource
from industrial_fire.domain.entities.classification_result import ClassificationResult


def test_normal_industrial_label_is_not_abnormal():
    result = ClassificationResult.new(
        thermal_event_id=uuid4(),
        label=ClassificationLabel.GAS_FLARE_NORMAL_INDUSTRIAL,
        confidence=0.9,
        reasoning="routine flare",
        model_source=ModelSource.RULE_BASED_V1,
        model_version="rule-based-v1.0",
    )
    assert result.is_abnormal is False


def test_other_labels_are_abnormal():
    for label in (
        ClassificationLabel.POTENTIAL_INDUSTRIAL_FIRE,
        ClassificationLabel.WILDFIRE,
        ClassificationLabel.UNKNOWN_NEEDS_REVIEW,
    ):
        result = ClassificationResult.new(
            thermal_event_id=uuid4(),
            label=label,
            confidence=0.5,
            reasoning="x",
            model_source=ModelSource.RULE_BASED_V1,
            model_version="rule-based-v1.0",
        )
        assert result.is_abnormal is True


def test_model_metrics_default_to_none():
    result = ClassificationResult.new(
        thermal_event_id=uuid4(),
        label=ClassificationLabel.WILDFIRE,
        confidence=0.5,
        reasoning="x",
        model_source=ModelSource.RULE_BASED_V1,
        model_version="rule-based-v1.0",
    )
    assert result.model_precision is None
    assert result.model_recall is None
    assert result.model_accuracy is None
    assert result.model_f1_macro is None


def test_model_metrics_are_stored_when_provided():
    result = ClassificationResult.new(
        thermal_event_id=uuid4(),
        label=ClassificationLabel.WILDFIRE,
        confidence=0.5,
        reasoning="x",
        model_source=ModelSource.XGBOOST_V1,
        model_version="xgboost-20260101000000",
        model_precision=0.8,
        model_recall=0.7,
        model_accuracy=0.75,
        model_f1_macro=0.74,
    )
    assert result.model_precision == 0.8
    assert result.model_recall == 0.7
    assert result.model_accuracy == 0.75
    assert result.model_f1_macro == 0.74
