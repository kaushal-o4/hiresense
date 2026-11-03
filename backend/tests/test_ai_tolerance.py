"""Model-output tolerance: a display-only label the model invents must not discard a whole analysis."""
from app.services.ai import ResumeSkillItem


def test_unknown_skill_category_is_mapped_not_rejected():
    assert ResumeSkillItem(name="Docker", category="DevOps").category == "tool"
    assert ResumeSkillItem(name="Python", category="Language").category == "programming_language"
    assert ResumeSkillItem(name="X", category="something new").category == "other"
    assert ResumeSkillItem(name="AWS", category="cloud").category == "cloud"
