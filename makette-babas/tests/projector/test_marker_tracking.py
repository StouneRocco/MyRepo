"""Tracking ArUco : pose complète d'une même image, lissage et rejets."""
import unittest
import numpy as np
from marker_tracking import MarkerTracker


class MarkerTrackingTests(unittest.TestCase):
    def setUp(self):
        self.tracker=MarkerTracker((1,2,3,4))
        self.pose={i:np.array([[x,y],[x+4,y],[x+4,y+4],[x,y+4]],dtype=float)
                   for i,(x,y) in enumerate([(0,0),(100,0),(100,100),(0,100)],1)}

    def test_missing_marker_never_combines_old_and_new_positions(self):
        self.assertIsNotNone(self.tracker.update(self.pose,0))
        for missing in self.pose:
            moved={i:p+50 for i,p in self.pose.items() if i!=missing}
            self.assertIsNone(self.tracker.update(moved,.1))
            np.testing.assert_array_equal(self.tracker.pose[1],self.pose[1])

    def test_reacquisition_after_loss_has_no_old_pose_drag(self):
        self.tracker.update(self.pose,0)
        moved={i:p+50 for i,p in self.pose.items()}
        result=self.tracker.update(moved,1)
        np.testing.assert_array_equal(result[1],moved[1])

    def test_short_interruptions_are_smoothed_with_alpha(self):
        self.tracker.update(self.pose,0)
        moved={i:p+20 for i,p in self.pose.items()}
        result=self.tracker.update(moved,.5)
        np.testing.assert_allclose(result[1],self.pose[1]+20*.15)

    def test_extra_markers_are_ignored_and_order_is_kept(self):
        observations={**self.pose,0:np.zeros((4,2)),7:np.ones((4,2))}
        result=self.tracker.update(observations,0)
        self.assertEqual(tuple(result),(1,2,3,4))

    def test_wrong_corner_shape_is_rejected(self):
        self.pose[3]=self.pose[3][:3]
        self.assertIsNone(self.tracker.update(self.pose,0))

    def test_reset_forgets_previous_pose(self):
        self.tracker.update(self.pose,0)
        self.tracker.reset()
        self.assertIsNone(self.tracker.pose)
        moved={i:p+20 for i,p in self.pose.items()}
        np.testing.assert_array_equal(self.tracker.update(moved,.1)[1],moved[1])

    def test_crossed_or_nonfinite_pose_is_rejected(self):
        self.pose[2],self.pose[3]=self.pose[3],self.pose[2]
        self.assertIsNone(self.tracker.update(self.pose,0))
        self.pose[1][0,0]=np.nan
        self.assertIsNone(self.tracker.update(self.pose,1))
