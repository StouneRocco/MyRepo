"""N'accepte que des poses complètes issues d'une même image caméra."""
import numpy as np


class MarkerTracker:
    def __init__(self, marker_ids, alpha=.15):
        self.marker_ids = tuple(marker_ids)
        self.alpha = alpha
        self.reset()

    def reset(self):
        self.pose = None
        self.last_seen = None

    def update(self, observations, now):
        if not all(marker in observations for marker in self.marker_ids):
            return None
        points = {marker: np.asarray(observations[marker], dtype=np.float32) for marker in self.marker_ids}
        if any(value.shape != (4, 2) or not np.isfinite(value).all() for value in points.values()):
            return None
        centers = np.array([points[marker].mean(axis=0) for marker in self.marker_ids])
        edges = np.roll(centers, -1, axis=0)-centers
        cross = edges[:, 0]*np.roll(edges[:, 1], -1)-edges[:, 1]*np.roll(edges[:, 0], -1)
        if not (np.all(cross > 1) or np.all(cross < -1)):
            return None
        # Après perte, ne pas lisser avec une pose datant d'avant le déplacement.
        if self.pose is not None and now-self.last_seen <= .5:
            points = {marker:self.alpha*value+(1-self.alpha)*self.pose[marker] for marker,value in points.items()}
        self.pose, self.last_seen = points, now
        return points
