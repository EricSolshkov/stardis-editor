"""
test_semantic_mapping.py — BodyEditor 语义映射函数测试

覆盖:
  - _semantic_to_side: 语义文本 → Side 枚举
  - _side_to_semantic: Side 枚举 → 语义文本
  - _side_to_cavities: Side + 朝向 → (inner_on, outer_on)
  - _inner_to_side / _outer_to_side: 腔体 → Side
  - UNKNOWN 降级显示
  - 往返: side → semantic → side 恒等
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "src"))

from models.scene_model import Side, NormalOrientation
from panels.property_panel import BodyEditor


class TestSemanticToSide:
    """语义文本 → Side 枚举 (FRONT=反法线侧)。"""

    def test_outward_outer_is_back(self):
        # 法线朝外: 外侧=法线侧=BACK
        assert BodyEditor._semantic_to_side("外侧", NormalOrientation.OUTWARD) == Side.BACK

    def test_outward_inner_is_front(self):
        # 法线朝外: 内侧=反法线=FRONT
        assert BodyEditor._semantic_to_side("内侧", NormalOrientation.OUTWARD) == Side.FRONT

    def test_outward_both_is_both(self):
        assert BodyEditor._semantic_to_side("两侧", NormalOrientation.OUTWARD) == Side.BOTH

    def test_inward_outer_is_front(self):
        # 法线朝内: 外侧=反法线=FRONT
        assert BodyEditor._semantic_to_side("外侧", NormalOrientation.INWARD) == Side.FRONT

    def test_inward_inner_is_back(self):
        # 法线朝内: 内侧=法线侧=BACK
        assert BodyEditor._semantic_to_side("内侧", NormalOrientation.INWARD) == Side.BACK

    def test_inward_both_is_both(self):
        assert BodyEditor._semantic_to_side("两侧", NormalOrientation.INWARD) == Side.BOTH

    def test_unknown_front(self):
        assert BodyEditor._semantic_to_side("FRONT", NormalOrientation.UNKNOWN) == Side.FRONT

    def test_unknown_back(self):
        assert BodyEditor._semantic_to_side("BACK", NormalOrientation.UNKNOWN) == Side.BACK

    def test_unknown_both(self):
        assert BodyEditor._semantic_to_side("BOTH", NormalOrientation.UNKNOWN) == Side.BOTH


class TestSideToSemantic:
    """Side 枚举 → 语义文本 (FRONT=反法线侧)。"""

    def test_outward_front_is_inner(self):
        # FRONT=反法线, 法线朝外 → 反法线=内侧
        assert BodyEditor._side_to_semantic(Side.FRONT, NormalOrientation.OUTWARD) == "内侧"

    def test_outward_back_is_outer(self):
        # BACK=法线侧, 法线朝外 → 法线=外侧
        assert BodyEditor._side_to_semantic(Side.BACK, NormalOrientation.OUTWARD) == "外侧"

    def test_outward_both_is_both(self):
        assert BodyEditor._side_to_semantic(Side.BOTH, NormalOrientation.OUTWARD) == "两侧"

    def test_inward_front_is_outer(self):
        # FRONT=反法线, 法线朝内 → 反法线=外侧
        assert BodyEditor._side_to_semantic(Side.FRONT, NormalOrientation.INWARD) == "外侧"

    def test_inward_back_is_inner(self):
        # BACK=法线侧, 法线朝内 → 法线=内侧
        assert BodyEditor._side_to_semantic(Side.BACK, NormalOrientation.INWARD) == "内侧"

    def test_inward_both_is_both(self):
        assert BodyEditor._side_to_semantic(Side.BOTH, NormalOrientation.INWARD) == "两侧"

    def test_unknown_front(self):
        assert BodyEditor._side_to_semantic(Side.FRONT, NormalOrientation.UNKNOWN) == "FRONT"

    def test_unknown_back(self):
        assert BodyEditor._side_to_semantic(Side.BACK, NormalOrientation.UNKNOWN) == "BACK"

    def test_unknown_both(self):
        assert BodyEditor._side_to_semantic(Side.BOTH, NormalOrientation.UNKNOWN) == "BOTH"


class TestRoundtrip:
    """往返: side → semantic → side 恒等。"""

    def test_all_sides_outward(self):
        for side in Side:
            semantic = BodyEditor._side_to_semantic(side, NormalOrientation.OUTWARD)
            recovered = BodyEditor._semantic_to_side(semantic, NormalOrientation.OUTWARD)
            assert recovered == side

    def test_all_sides_inward(self):
        for side in Side:
            semantic = BodyEditor._side_to_semantic(side, NormalOrientation.INWARD)
            recovered = BodyEditor._semantic_to_side(semantic, NormalOrientation.INWARD)
            assert recovered == side

    def test_all_sides_unknown(self):
        for side in Side:
            semantic = BodyEditor._side_to_semantic(side, NormalOrientation.UNKNOWN)
            recovered = BodyEditor._semantic_to_side(semantic, NormalOrientation.UNKNOWN)
            assert recovered == side


# ═══════════════ 腔体 ↔ Side 映射 ═══════════════

class TestSideToCavities:
    """_side_to_cavities: Side + 朝向 → (inner_on, outer_on)。"""

    # BOTH → 两侧均启用
    def test_both_outward(self):
        assert BodyEditor._side_to_cavities(Side.BOTH, NormalOrientation.OUTWARD) == (True, True)

    def test_both_inward(self):
        assert BodyEditor._side_to_cavities(Side.BOTH, NormalOrientation.INWARD) == (True, True)

    def test_both_unknown(self):
        assert BodyEditor._side_to_cavities(Side.BOTH, NormalOrientation.UNKNOWN) == (True, True)

    # OUTWARD: FRONT=反法线=内侧, BACK=法线=外侧
    def test_front_outward(self):
        assert BodyEditor._side_to_cavities(Side.FRONT, NormalOrientation.OUTWARD) == (True, False)

    def test_back_outward(self):
        assert BodyEditor._side_to_cavities(Side.BACK, NormalOrientation.OUTWARD) == (False, True)

    # INWARD: FRONT=反法线=外侧, BACK=法线=内侧
    def test_front_inward(self):
        assert BodyEditor._side_to_cavities(Side.FRONT, NormalOrientation.INWARD) == (False, True)

    def test_back_inward(self):
        assert BodyEditor._side_to_cavities(Side.BACK, NormalOrientation.INWARD) == (True, False)

    # UNKNOWN: 默认同 OUTWARD, FRONT=内, BACK=外
    def test_front_unknown(self):
        assert BodyEditor._side_to_cavities(Side.FRONT, NormalOrientation.UNKNOWN) == (True, False)

    def test_back_unknown(self):
        assert BodyEditor._side_to_cavities(Side.BACK, NormalOrientation.UNKNOWN) == (False, True)


class TestInnerOuterToSide:
    """_inner_to_side / _outer_to_side 映射。"""

    def test_inner_outward(self):
        # 法线朝外: 内侧=反法线=FRONT
        assert BodyEditor._inner_to_side(NormalOrientation.OUTWARD) == Side.FRONT

    def test_inner_inward(self):
        # 法线朝内: 内侧=法线侧=BACK
        assert BodyEditor._inner_to_side(NormalOrientation.INWARD) == Side.BACK

    def test_inner_unknown(self):
        # UNKNOWN 默认同 OUTWARD: 内侧=FRONT
        assert BodyEditor._inner_to_side(NormalOrientation.UNKNOWN) == Side.FRONT

    def test_outer_outward(self):
        # 法线朝外: 外侧=法线侧=BACK
        assert BodyEditor._outer_to_side(NormalOrientation.OUTWARD) == Side.BACK

    def test_outer_inward(self):
        # 法线朝内: 外侧=反法线=FRONT
        assert BodyEditor._outer_to_side(NormalOrientation.INWARD) == Side.FRONT

    def test_outer_unknown(self):
        # UNKNOWN 默认同 OUTWARD: 外侧=BACK
        assert BodyEditor._outer_to_side(NormalOrientation.UNKNOWN) == Side.BACK


class TestCavityRoundtrip:
    """Side → cavities → Side 往返一致。"""

    def test_roundtrip_outward(self):
        for side in Side:
            inner_on, outer_on = BodyEditor._side_to_cavities(side, NormalOrientation.OUTWARD)
            if inner_on and outer_on:
                recovered = Side.BOTH
            elif inner_on:
                recovered = BodyEditor._inner_to_side(NormalOrientation.OUTWARD)
            else:
                recovered = BodyEditor._outer_to_side(NormalOrientation.OUTWARD)
            assert recovered == side

    def test_roundtrip_inward(self):
        for side in Side:
            inner_on, outer_on = BodyEditor._side_to_cavities(side, NormalOrientation.INWARD)
            if inner_on and outer_on:
                recovered = Side.BOTH
            elif inner_on:
                recovered = BodyEditor._inner_to_side(NormalOrientation.INWARD)
            else:
                recovered = BodyEditor._outer_to_side(NormalOrientation.INWARD)
            assert recovered == side

    def test_roundtrip_unknown(self):
        for side in Side:
            inner_on, outer_on = BodyEditor._side_to_cavities(side, NormalOrientation.UNKNOWN)
            if inner_on and outer_on:
                recovered = Side.BOTH
            elif inner_on:
                recovered = BodyEditor._inner_to_side(NormalOrientation.UNKNOWN)
            else:
                recovered = BodyEditor._outer_to_side(NormalOrientation.UNKNOWN)
            assert recovered == side
