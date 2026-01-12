"""
Central registry for available gestures and actions.

This module maintains the definitive lists of supported gestures and actions
in the Handsi system. Update these lists when adding new gestures or actions.
"""

# All available gestures (alphabetically sorted)
# Update this list when adding new gestures to rules.py
AVAILABLE_GESTURES = [
    "fist",
    "index_pinch",
    "middle_pinch",
    "open_hand",
    "pinky_pinch",
    "ring_pinch",
    "swipe",
    "thumbs_down",
    "thumbs_up",
    "two_finger_pinch",
    "two_fingers_point",
    "two_hands_open",
    "two_hands_pinch",
]

# All available actions (alphabetically sorted)
# Update this list when adding new actions to executor.py
AVAILABLE_ACTIONS = [
    "click",
    "continuous_scroll",
    "continuous_zoom",
    "disable_latch",
    "double_click",
    "enable_latch",
    "mouse_move",
    "right_click",
    "scroll_down",
    "scroll_up",
    "switch_desktop",
    "zoom_in",
    "zoom_out",
]
