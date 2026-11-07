"""Ensemble / soft voting (Stage 8.5): several models answer, and their probabilities are averaged.

Different models make DIFFERENT mistakes. Logistic regression weighs words and word pairs; Bernoulli
Naive Bayes also counts the words that are missing; the linear SVM only cares about borderline sentences.
When one is unsure or wrong, the others often outvote it. "Soft" voting averages their probabilities
(a confident model counts more than a hesitant one); "hard" voting would only count each one's top answer.

It only pays off when the members are good AND disagree on different sentences; three copies of the
same model would just repeat the same mistakes.
"""
import json
from pathlib import Path


class Ensemble:
    kind = "ensemble"
    # Cut-off sweep (5-fold, as MAVERICK runs / hard cases): 0.3 -> 84.5% / 75%, 0.4 -> 85.0% / 69%,
    # 0.5 -> 84.5% / 61%. Averaged confidences are lower than one model's, so a lower cut-off fits.
    threshold = 0.3
    MEMBERS = ("logistic_regression", "bernoulli_nb", "linear_svm")  # picked in 8.5, see PROGRESS.md

    def __init__(self, members: tuple[str, ...] = MEMBERS):
        self.member_kinds = members
        self.members = []

    def classes(self) -> dict:
        from maverick.brain import MODELS  # here, not at the top: MODELS itself lists Ensemble
        return MODELS

    def fit(self, examples) -> "Ensemble":
        self.members = [self.classes()[kind]().fit(examples) for kind in self.member_kinds]
        return self

    def predict_proba(self, tokens) -> dict[str, float]:
        total: dict[str, float] = {}
        for member in self.members:
            for label, p in member.predict_proba(tokens).items():
                total[label] = total.get(label, 0.0) + p / len(self.members)
        return total

    def predict(self, tokens) -> tuple[str, float]:
        probs = self.predict_proba(tokens)
        label = max(probs, key=probs.get)
        return label, probs[label]

    def member_path(self, path: Path, kind: str) -> Path:
        return path.with_name(f"{path.stem}.{kind}.json")  # brain.json -> brain.logistic_regression.json

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        for kind, member in zip(self.member_kinds, self.members):
            member.save(self.member_path(path, kind))
        path.write_text(json.dumps({"kind": self.kind, "members": list(self.member_kinds)}), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Ensemble":
        data = json.loads(path.read_text(encoding="utf-8"))
        model = cls(tuple(data["members"]))
        model.members = [model.classes()[kind].load(model.member_path(path, kind)) for kind in model.member_kinds]
        return model
