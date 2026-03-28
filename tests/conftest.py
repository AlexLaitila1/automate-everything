import pytest

from skills.blueprint.models import BlueprintDimensions, Opening, WallSegment


@pytest.fixture
def simple_house() -> BlueprintDimensions:
    """A simple 12m × 8m rectangular house with 2 windows and 1 door."""
    return BlueprintDimensions(
        wall_segments=(
            WallSegment("north wall", 12.0),
            WallSegment("east wall", 8.0),
            WallSegment("south wall", 12.0),
            WallSegment("west wall", 8.0),
        ),
        wall_height_m=2.7,
        scale_description="1:100",
        openings=(
            Opening("window", 1.2, 1.0),
            Opening("window", 1.2, 1.0),
            Opening("door", 0.9, 2.1),
        ),
    )
