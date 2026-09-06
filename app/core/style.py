"""The one fixed category -> color mapping (and chrome colors) reused by every chart across the whole
project — notebooks 1/3/4/6 and every chart in this app. Keeping it in one place means a chart never
disagrees with another about what color "Category B" is.
"""

CATEGORY_COLORS = {
    "A": "#2a78d6",     # blue
    "B": "#eb6834",     # orange
    "C": "#1baf7a",     # aqua
    "Misc": "#eda100",  # yellow
}
GRIDLINE = "#e1e0d9"      # hairline gridline color
AXIS_INK = "#c3c2b7"      # axis border line color
TEXT_PRIMARY = "#0b0b0b"  # main text color (titles, data labels)
TEXT_MUTED = "#898781"    # muted color for axis tick labels
