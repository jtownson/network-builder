from typing import List
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.api.dependencies import get_db_conn

router = APIRouter(prefix="/v1/orgs", tags=["connections"])


class RankedUser(BaseModel):
    user_id: str = Field(description="User id in the ranking for this cluster.")
    distance: float = Field(
        description=(
            "pgvector cosine distance (`<=>`) between this user's cluster-specific mean embedding "
            "and the target user's cluster-specific mean embedding. "
            "`0.0` means most similar. This is user-to-target distance, not distance to centroid."
        )
    )
    message_count: int = Field(
        description="Number of messages contributing to this user's mean embedding in this cluster."
    )


class UserCentroidResult(BaseModel):
    cluster_id: UUID = Field(description="Active cluster id that includes the target user.")
    users: List[RankedUser] = Field(
        description=(
            "Users in this cluster ranked by `distance` ascending; ties break by `user_id` ascending."
        )
    )


class UserCentroidsResponse(BaseModel):
    org_id: str = Field(description="Organization id.")
    user_id: str = Field(description="Target user id used for the ranking comparison.")
    centroids: List[UserCentroidResult] = Field(
        description=(
            "One result per active cluster containing the target user, with in-cluster user rankings."
        )
    )


@router.get(
    "/{org_id}/users/{user_id}/connections",
    summary="Rank users by distance to a target user within each shared active cluster",
    description=(
        "List other users in order of semantic connection to the target user."
        "For each active cluster that contains the target user, this endpoint computes one vector per "
        "user as `AVG(message_embeddings.embedding)` over messages assigned to that cluster. "
        "It then ranks users by pgvector cosine distance (`<=>`) to "
        "the target user's vector in the same cluster."
    ),
    response_description=(
        "Per-cluster user rankings where `distance` is cosine distance to the target user (ascending)."
    ),
    response_model=UserCentroidsResponse,
)
def get_user_centroids(
    org_id: str = Path(description="Organization id."),
    user_id: str = Path(description="Target user id for per-cluster rankings."),
    conn: psycopg.Connection = Depends(get_db_conn),
) -> UserCentroidsResponse:
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH target_clusters AS (
              SELECT uc.cluster_id, c.model_version
              FROM user_cluster uc
              JOIN clusters c
                ON c.org_id = uc.org_id
               AND c.cluster_id = uc.cluster_id
              WHERE uc.org_id = %s
                AND uc.user_id = %s
                AND c.is_active = TRUE
            ),
            user_cluster_vectors AS (
              SELECT
                tc.cluster_id,
                m.user_id,
                AVG(me.embedding)::vector AS user_vec,
                COUNT(*)::bigint AS message_count
              FROM target_clusters tc
              JOIN message_cluster mc
                ON mc.org_id = %s
               AND mc.cluster_id = tc.cluster_id
              JOIN messages m
                ON m.org_id = mc.org_id
               AND m.message_id = mc.message_id
              JOIN message_embeddings me
                ON me.org_id = mc.org_id
               AND me.message_id = mc.message_id
               AND me.model_version = tc.model_version
              GROUP BY tc.cluster_id, m.user_id
            ),
            target_user_vectors AS (
              SELECT cluster_id, user_vec AS target_vec
              FROM user_cluster_vectors
              WHERE user_id = %s
            )
            SELECT
              ucv.cluster_id,
              ucv.user_id,
              (ucv.user_vec <=> tuv.target_vec) AS distance,
              ucv.message_count
            FROM user_cluster_vectors ucv
            JOIN target_user_vectors tuv
              ON tuv.cluster_id = ucv.cluster_id
            ORDER BY ucv.cluster_id, distance ASC, ucv.user_id ASC
            """,
            (org_id, user_id, org_id, user_id),
        )
        rows = cur.fetchall()

    centroids: List[UserCentroidResult] = []
    current_cluster: UUID | None = None
    current_users: List[RankedUser] = []

    for cluster_id, ranked_user_id, distance, message_count in rows:
        parsed_cluster_id = UUID(str(cluster_id))
        if current_cluster is None:
            current_cluster = parsed_cluster_id
        if parsed_cluster_id != current_cluster:
            centroids.append(UserCentroidResult(cluster_id=current_cluster, users=current_users))
            current_cluster = parsed_cluster_id
            current_users = []

        current_users.append(
            RankedUser(
                user_id=ranked_user_id,
                distance=float(distance),
                message_count=int(message_count),
            )
        )

    if current_cluster is not None:
        centroids.append(UserCentroidResult(cluster_id=current_cluster, users=current_users))

    return UserCentroidsResponse(org_id=org_id, user_id=user_id, centroids=centroids)
