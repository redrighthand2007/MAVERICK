import numpy as np

from maverick.agents.search import ops
from maverick.agents.search.agent import SearchAgent
from maverick.brain.cluster import KMeans, best_kmeans, pair_agreement, silhouette

# History (python -m maverick.brain.cluster, made-up names with 3 one-offs): one group per extension 94.9%,
# k-means 92.4% with the file kind at full weight, 96.8% without it.
MIN_AGREEMENT = 0.95


def blobs(seed=0):
    """Three clearly separate clouds of 20 points."""
    rng = np.random.default_rng(seed)
    centres = np.array([[0, 0], [10, 0], [0, 10]])
    return np.vstack([c + rng.normal(0, 0.5, size=(20, 2)) for c in centres]), np.repeat([0, 1, 2], 20)


def test_kmeans_finds_separate_clouds():
    X, truth = blobs()
    assert pair_agreement(truth, KMeans(3).fit(X).labels) == 1.0


def test_restarts_never_make_it_worse():
    X, _ = blobs()
    assert KMeans(3, restarts=5).fit(X).inertia <= KMeans(3, restarts=1).fit(X).inertia + 1e-9


def test_silhouette_prefers_the_true_number_of_groups():
    X, _ = blobs()
    assert best_kmeans(X).k == 3
    assert silhouette(X, KMeans(3).fit(X).labels) > silhouette(X, KMeans(2).fit(X).labels)


def test_silhouette_of_one_group_is_zero():
    assert silhouette(np.zeros((5, 2)), [0] * 5) == 0.0


def test_pair_agreement_ignores_group_numbers():
    assert pair_agreement([0, 0, 1, 1], [5, 5, 9, 9]) == 1.0
    assert pair_agreement([0, 0, 1, 1], [0, 1, 0, 1]) < 0.5


def test_name_words_drop_numbers_and_split_camel_case():
    assert ops.name_words("Invoice_March-2024.pdf") == ["invoice", "march", "ext:pdf", "kind:document"]
    assert ops.name_words("ChromeSetup.exe") == ["chrome", "setup", "ext:exe", "kind:installer"]
    assert ops.name_words("README") == ["readme", "kind:other"]


def test_group_titles():
    assert ops.group_title(["invoice_may.pdf", "invoice_june.pdf"]) == "invoice (pdf)"
    assert ops.group_title(["setup.exe", "vlc.exe", "7z.msi"]) == "installers"
    assert ops.group_title(["a.xyz", "b.xyz"]) == ".xyz files"


def test_sample_groups_beat_one_group_per_extension():
    names = [n for _, files in ops.SAMPLE_GROUPS for n in files]
    truth = [g for g, files in ops.SAMPLE_GROUPS for _ in files]
    X, _ = ops.vectors(names)
    by_ext = [n.rsplit(".", 1)[-1].lower() for n in names]
    found = pair_agreement(truth, best_kmeans(X).labels)
    assert found >= MIN_AGREEMENT
    assert found > pair_agreement(truth, by_ext)


def test_group_a_folder_reads_only(tmp_path):
    names = ["invoice_may.pdf", "invoice_june.pdf", "invoice_july.pdf", "IMG_1.jpg", "IMG_2.jpg", "IMG_3.jpg",
             "setup.exe", "notes.txt", "desktop.ini"]
    for n in names:
        (tmp_path / n).write_text("x")
    result = ops.group(str(tmp_path))
    assert result.success
    groups = {title: set(members) for title, members in result.data["groups"]}
    assert groups["invoice (pdf)"] == {"invoice_may.pdf", "invoice_june.pdf", "invoice_july.pdf"}
    assert "desktop.ini" not in str(result.data["groups"])  # hidden Windows file, skipped
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(names)  # nothing moved


def test_too_few_files(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    assert "nothing to group" in ops.group(str(tmp_path)).message


def test_the_agent_understands_grouping_requests():
    agent = SearchAgent()
    intent = agent.parse("group the files in my downloads")
    assert intent.operation == "group" and intent.args["root"].endswith("Downloads")
    assert agent.parse("organize my desktop files").args["root"].endswith("Desktop")
    assert agent.parse("find pdf files in downloads").operation == "find"
    assert agent.parse("group policy settings") is None
