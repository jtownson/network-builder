# Network builder clustering implementation

The network builder service uses an **online, centroid-based clustering** method over input message embeddings (768 element vectors), with cosine distance.

In essence, a users' messages are mapped to vectors in a 768 dimension space, and clusters
of such vectors formed to understand which messages are semantically similar. This then 
allows a user-based query to find other users who are talking about the same thing (even
though those users might not actually be talking to each other, or to anybody).  

### 1) Notation

- Message embedding: \(x \in \mathbb{R}^{768}\)
- Cluster centroid: \(c_k \in \mathbb{R}^{768}\)
- Effective cluster count: \(n_k\)
- Cosine similarity: \(\cos(x, c_k)\)
- Cosine distance: \(d(x, c_k) = 1 - \cos(x, c_k)\)

### Message embedding

An incoming message, \(m\), is run through an embedding and L2-normalized:

\[
    x = embed(m)
\]
\[
\hat{x} = \frac{x}{\lVert x \rVert} = \frac{x}{\sqrt{x_1^2 + x_2^2 + ... + x_{768}^2}}
\]

Cluster centroids are similarly normalized.

### Candidate cluster search

Given an input embedding, active cluster centroids are queried to find the nearest centroid to the message, subject to the constraint that this cluster must not be further away than a certain threshold distance, \(d_{\text{th}} = 1 - s_{\text{th}} = 0.22\).

If we assume this is the first message received, or there are no nearby message clusters
then this message will be used to initialize a new message cluster centred at \(\hat{x}\). Otherwise, we will find a
cluster. Thus, in either case we end up with a cluster \(c_x\) and an associated distance between the message and the centre of its cluster \(d_{\hat{x}} = d(\hat{x}, c_x)\).


### Confidence

We can think of the similarity between a message and a cluster centroid as the confidence in how strongly that message is part of the cluster. 
For a newly created cluster, where the originating message and
the cluster centroid are co-located, the confidence is \(1\). Messages on the 
periphery of a cluster have lower confidence. Beyond the distance threshold, \(d_{th}\), messages are excluded from that cluster.

Across a set of user messages, we can sum this confidence value to obtain a 
participation score for the user.

### Centroid Update (Online Capped Mean)

The arrival of a new message and assignment to a cluster will skew the centroid
of that cluster. The cluster centroid position is the mean position of the messages within the cluster. Given the arrival rate of messages could be high, centroid updates are computed using a running or _online_ mean algorithm.

If \(c_n\) is the centroid (i.e. mean) position after \(n\) points and a new point \(x\) arrives then:

\[
c_{n+1} = \frac{n c_k + \hat{x}}{n + 1}
\]

In practice, we define
\[
n_{\text{eff}} = \min(n, \text{cap})
\]

where \(cap\) is a parameter that caps the value of \(n\) and allows the centroid
to remain adaptable to new messages, preventing a large backlog of legacy messages from gumming up the system. 

### User-Cluster Accumulation

For each message assignment:

- `message_cluster.confidence` stores per-message confidence.
- `user_cluster.participation_score` is incremented by that confidence.
- `user_cluster.message_count` increments by 1.

So for user \(u\), cluster \(k\):

\[
\text{participation\_score}_{u,k} = \sum_{m \in (u,k)} \text{confidence}_m
\]

### Centroids API Distance Ranking

The `/users/{user_id}/connections` endpoint returns, for each active cluster that the
target user belongs to, other user ids sorted by cosine distance to that target user within
the same cluster.

Let \(u\) be a target user id.

1. Select active clusters, \(\mathcal{K}_u\) containing \(u\) (from `user_cluster` joined to `clusters`):

2. For each cluster \(k \in \mathcal{K}_u\), compute an average embedding vector, \(v_{u,k}\) for each user, \(u\), that has messages in the cluster:
\[
v_{u,k} = \frac{1}{|M_{u,k}|}\sum_{m \in M_{u,k}} embedding_m
\]

where \(M_{u,k}\) is the set of user \(u\)'s messages assigned to cluster \(k\), so that \(|M_{u,k}|\) is the count of user messages in the cluster.

Average user embeddings should also be normalized to give:
\[
\hat{v}_{u,k} = \frac{v_{u,k}}{\lVert v_{u,k} \rVert}
\]

Within the context of each cluster, we can now compute a pairwise distance between the given target user and the other \(n\) users:
\[
d_k(u,u') = (d_{k1}, d_{k2}, ..., d_{kn})
\]

These \(d\) values can then be sorted (in ascending order) to give a list of users with the closest semantic connection to the target user.

### References

- pgvector README (cosine distance operator `<=>`, and `cosine_similarity = 1 - cosine_distance`): https://github.com/pgvector/pgvector
- MacQueen (1967), original k-means / online centroid-update formulation: https://projecteuclid.org/euclid.bsmsp/1200512992
- Sculley (2010), web-scale / mini-batch k-means (streaming centroid updates): https://doi.org/10.1145/1772690.1772862
- scikit-learn clustering guide (MiniBatchKMeans overview): https://scikit-learn.org/stable/modules/clustering.html
- Hornik et al. (2012), spherical k-means and cosine-based prototype clustering: https://www.jstatsoft.org/article/view/v050i10
