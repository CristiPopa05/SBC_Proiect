from threading import Lock
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import numpy as np
import torch

from detection_api import predict_sign
from gtsrb_classifier import CropPrediction, classify_crops


class SignConfirmationTests(TestCase):
    def setUp(self):
        self.frame = np.zeros((80, 80, 3), dtype=np.uint8)

    def test_a_single_confident_crop_does_not_confirm_a_class(self):
        classifier = Mock(return_value=torch.tensor([[12., 0., 0.], [0., 10., 0.], [0., 0., 9.]]))
        self.assertEqual(classify_crops(classifier, self.frame, [(10, 10, 60, 60)]), {})

    def test_two_matching_views_allow_a_classification(self):
        classifier = Mock(return_value=torch.tensor([[0., 9., 0.], [0., 10., 0.], [8., 0., 0.]]))
        prediction = classify_crops(classifier, self.frame, [(10, 10, 60, 60)])[0]
        self.assertEqual(prediction.class_id, 1)
        self.assertGreater(prediction.confidence, 0.99)
        self.assertGreater(prediction.margin, 0.99)

    def test_reclassification_does_not_inherit_the_original_score(self):
        model = Mock()
        boxes = SimpleNamespace(
            conf=torch.tensor([0.97, 0.82]), cls=torch.tensor([0, 1]),
            xyxy=torch.tensor([[10, 10, 60, 60], [20, 20, 60, 60]]),
        )
        model.predict.return_value = [
            SimpleNamespace(boxes=boxes, names={0: "Speed Limit 80", 1: "Parking"})
        ]
        classifier = (Mock(), {5: {"kind": "speed", "value": 80}, 7: {"kind": "speed", "value": 100}})
        with patch("detection_api.classify_crops", return_value={0: CropPrediction(7, 0.97, 0.95)}):
            result = predict_sign(self.frame, (model, "cpu", Lock()), 640, 0.40, classifier)
        self.assertEqual(result, {"kind": "parking"})

    def test_a_small_oncoming_sign_requires_crop_confirmation(self):
        model = Mock()
        boxes = SimpleNamespace(
            conf=torch.tensor([0.85]), cls=torch.tensor([0]),
            xyxy=torch.tensor([[10, 10, 34, 34]]),
        )
        model.predict.return_value = [SimpleNamespace(boxes=boxes, names={0: "Yield to oncoming traffic"})]
        sign = {"kind": "oncoming_has_priority"}
        detector = model, "cpu", Lock()
        classifier = Mock(), {44: sign}
        with patch("detection_api.classify_crops", return_value={}):
            self.assertIsNone(predict_sign(self.frame, detector, 640, 0.40, classifier))
        with patch("detection_api.classify_crops", return_value={0: CropPrediction(44, 0.83, 0.65)}):
            self.assertEqual(predict_sign(self.frame, detector, 640, 0.40, classifier), sign)
