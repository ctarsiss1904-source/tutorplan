"""Page-specific, source-grounded FAQ generation for regional tutoring pages."""

from __future__ import annotations

import hashlib
import re
from html import escape


def source_record(sheet, row: int) -> dict[str, str]:
    """Return only fields that are present in the supplied workbook."""
    state_cell = str(sheet.cell(row, 6).value or "").strip()
    action_cell = str(sheet.cell(row, 9).value or "").strip()
    state = state_cell.split(" | ", 1)[0].strip()
    if " | " in action_cell:
        action, metric = (part.strip() for part in action_cell.split(" | ", 1))
    else:
        action = action_cell
        progression = str(sheet.cell(row, 10).value or "").strip()
        metric = progression if progression and len(progression) <= 80 and "→" not in progression else action
    return {
        "keyword": str(sheet.cell(row, 1).value or "").strip(),
        "elementary": str(sheet.cell(row, 2).value or "").strip(),
        "middle": str(sheet.cell(row, 3).value or "").strip(),
        "high": str(sheet.cell(row, 4).value or "").strip(),
        "state": state,
        "observed": str(sheet.cell(row, 7).value or "").strip(),
        "cause": str(sheet.cell(row, 8).value or "").strip(),
        "action": action,
        "metric": metric,
        "content": sheet.cell(row, 11).value or "",
    }


def _plain(value: str, limit: int = 132) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" .。")
    if len(value) <= limit:
        return value
    cutoff = max(value.rfind(". ", 0, limit), value.rfind(";", 0, limit), value.rfind("→", 0, limit))
    return value[: cutoff if cutoff > 36 else limit].rstrip(" ,;·")


def _fallback(value: str, fallback: str) -> str:
    return _plain(value) if value else fallback


def _index(record: dict[str, str], context: str | None = None) -> int:
    source = "|".join(record.get(key, "") for key in ("keyword", "state", "observed", "cause", "action", "metric"))
    source += "|" + (context or "")
    return int(hashlib.sha256(source.encode("utf-8")).hexdigest()[:8], 16)


def faq_section(
    record: dict[str, str],
    *,
    directory: bool = False,
    context: str | None = None,
) -> str:
    """Create three visible FAQs tied to one workbook record.

    The templates intentionally rotate their starting point, while every FAQ
    carries a distinct source fact from the page record.  This avoids location-
    only substitutions and keeps the answers tied to observable learning scenes.
    """
    state = _plain(_fallback(record.get("state", ""), "현재 학습 장면"), 64)
    observed = _plain(_fallback(record.get("observed", ""), "학생이 멈춘 실제 행동"), 70)
    cause = _plain(_fallback(record.get("cause", ""), "다음 행동을 정하는 기준이 없는지"), 70)
    action = _plain(_fallback(record.get("action", ""), "한 가지 행동을 직접 해 보게 하는 것"), 72)
    metric = _plain(_fallback(record.get("metric", ""), "같은 장면에서 달라진 행동"), 64)
    page_name = context or _fallback(record.get("keyword", ""), "이 페이지")
    variant = _index(record, context)

    if directory:
        q1 = f"하위 지역 페이지를 볼 때 ‘{state}’와 비슷한 장면은 무엇부터 확인해야 하나요?"
        a1 = f"먼저 ‘{observed}’가 실제로 나타나는지 확인하는 것이 좋습니다. 원인을 넓게 추측하기보다 ‘{cause}’라는 기준으로 해당 지역의 본문을 읽어야 합니다."
        q2 = f"‘{state}’를 다룰 선생님을 고를 때 수업에서 확인할 장면은 무엇인가요?"
        a2 = f"첫 수업에서는 선생님이 ‘{action}’을 직접 시도하게 하는지 살펴보면 됩니다. 학생 대신 해결하기보다 학생의 행동 변화를 관찰하는 방식이어야 합니다."
        q3 = f"하위 페이지의 ‘{metric}’ 기록은 어떻게 다음 수업으로 이어 볼 수 있나요?"
        a3 = f"한 번의 결과로 결론내리지 말고, 같은 장면에서 ‘{metric}’이 다시 확인되는지 비교해야 합니다. 기록은 다음 행동을 정하는 근거로만 사용합니다."
    else:
        question_1 = (
            f"‘{observed}’가 이어질 때, 학생은 어느 단계부터 점검해야 하나요?",
            f"‘{state}’ 상황에서 학생의 공부 방법을 어떻게 확인할 수 있나요?",
            f"학생이 ‘{observed}’ 장면에서 멈춘다면 먼저 무엇을 바꿔야 하나요?",
            f"‘{state}’ 상황이 반복될 때 혼자 확인해 볼 수 있는 기준은 무엇인가요?",
            f"공부 중 ‘{observed}’ 행동이 보이면 원인을 어떻게 좁혀야 하나요?",
            f"‘{state}’를 단순한 습관 문제로 보기 전에 어떤 장면을 기록해야 하나요?",
            f"학생이 다음 단계로 넘어가지 못하고 ‘{observed}’ 한다면 무엇을 확인하나요?",
            f"‘{state}’를 줄이려면 결과보다 어떤 행동부터 살펴봐야 하나요?",
        )
        answer_1 = (
            f"핵심은 ‘{cause}’인지 확인하는 데 있습니다. 먼저 ‘{action}’이라는 행동을 짧게 해 본 뒤, ‘{metric}’이 달라지는지를 기록하면 학생이 혼자 조정할 수 있는 범위를 구분할 수 있습니다.",
            f"첫 판단 기준은 ‘{cause}’입니다. ‘{observed}’ 장면을 한 번 적어 두고 ‘{action}’을 적용한 뒤, ‘{metric}’을 전후로 비교해 보세요.",
            f"원인을 넓게 해석하기보다 ‘{cause}’부터 봐야 합니다. 학생이 ‘{action}’이라는 행동을 직접 실행했을 때 ‘{metric}’에 어떤 변화가 남는지 확인하는 방식이 좋습니다.",
            f"‘{cause}’가 있는지를 먼저 확인해야 합니다. 그다음 ‘{action}’을 시도하고, 같은 상황에서 ‘{metric}’이 유지되는지 보면 됩니다.",
        )
        question_2 = (
            f"‘{state}’를 다룰 때 선생님은 어떤 도움부터 제공하는 편이 좋나요?",
            f"‘{observed}’가 보이는 학생에게는 어떤 수업 방식의 선생님이 필요할까요?",
            f"선생님이 ‘{state}’를 대신 해결하지 않고 지도하려면 무엇을 해야 하나요?",
            f"‘{cause}’가 의심될 때 체험 수업에서 선생님의 어떤 반응을 봐야 하나요?",
            f"‘{state}’를 다루는 수업에서 설명보다 먼저 확인할 것은 무엇인가요?",
            f"학생이 ‘{observed}’ 할 때 선생님은 어느 지점까지 개입해야 하나요?",
            f"‘{state}’ 상황의 학생은 수업 속도를 어떤 기준으로 조절해야 하나요?",
            f"선생님 선택 전 ‘{observed}’ 장면을 어떻게 전달하면 좋을까요?",
        )
        answer_2 = (
            f"첫 개입은 “{action}”처럼 학생이 직접 해 볼 수 있는 행동이어야 합니다. 선생님은 ‘{observed}’ 장면을 본 뒤 필요한 만큼만 돕고, ‘{metric}’으로 변화 여부를 확인하는 편이 좋습니다.",
            f"선생님은 ‘{cause}’를 확인할 수 있는 과제를 먼저 제시해야 합니다. 이후 ‘{action}’을 시도하게 하고, 결과가 아니라 ‘{metric}’이 달라졌는지를 함께 봐야 합니다.",
            f"설명을 늘리기보다 ‘{action}’이라는 행동을 실행하게 하는 수업이 맞습니다. 학생이 ‘{observed}’ 할 때까지 기다린 뒤, 필요한 지점만 질문으로 돕는지를 확인하세요.",
            f"수업에서는 ‘{observed}’ 장면을 숨기지 않고 관찰해야 합니다. 선생님이 ‘{action}’이라는 행동을 제안한 뒤 ‘{metric}’을 기준으로 다음 도움을 정하는 방식이 적절합니다.",
        )
        question_3 = (
            f"‘{metric}’은 다음 회차에서 어떻게 활용하면 좋나요?",
            f"{page_name} 학습 장면에서 ‘{action}’이 실제로 자리 잡았는지는 어떻게 알 수 있나요?",
            f"‘{state}’ 상황이 다시 나타날 때 이전 기록은 어떻게 써야 하나요?",
            f"학생이 ‘{action}’을 혼자 적용할 수 있는지 다음 단계에서 어떻게 확인하나요?",
            f"‘{metric}’이 좋아졌더라도 수업 방식을 바로 바꿔도 될까요?",
            f"다음 과제나 복습에서 ‘{observed}’ 장면을 다시 확인하는 방법은 무엇인가요?",
            f"‘{state}’를 다룬 뒤 가정에서 남길 수 있는 짧은 기록은 무엇인가요?",
            f"한 번의 수업 뒤 ‘{cause}’가 해결됐다고 판단해도 될까요?",
        )
        answer_3 = (
            f"‘{metric}’은 같은 장면을 다시 만났을 때 비교하는 용도로 쓰는 것이 좋습니다. ‘{action}’이라는 행동을 새 과제나 복습에서도 스스로 선택하는지 확인해야 합니다.",
            f"다음 회차에는 ‘{observed}’ 장면을 다시 한 번 확인하세요. ‘{action}’이라는 행동을 교사의 추가 설명 없이 실행하고 ‘{metric}’이 유지되면 독립 적용의 근거가 됩니다.",
            f"기록은 ‘{state}’가 있었는지뿐 아니라 ‘{action}’이라는 행동 뒤 무엇이 달라졌는지 남겨야 합니다. ‘{metric}’을 같은 기준으로 비교해야 다음 계획을 정할 수 있습니다.",
            f"한 번 잘된 결과만으로 판단하지 않는 편이 좋습니다. 다른 과제에서도 ‘{action}’이라는 행동을 시도했을 때 ‘{metric}’이 비슷하게 나타나는지 확인해야 합니다.",
        )
        q1 = question_1[variant % len(question_1)]
        a1 = answer_1[(variant // 3) % len(answer_1)]
        q2 = question_2[(variant // 5) % len(question_2)]
        a2 = answer_2[(variant // 7) % len(answer_2)]
        q3 = question_3[(variant // 11) % len(question_3)]
        a3 = answer_3[(variant // 13) % len(answer_3)]

    # Each answer opens with the page's distinct learning situation.  This keeps
    # the visible answer useful out of context and prevents generic answer
    # openings from repeating across the regional page set.
    a1 = f"{page_name} 페이지에서 다루는 ‘{state}’ 상황에서는 {a1}"
    a2 = f"{page_name} 수업에서 ‘{state}’ 상황이 보일 때는 {a2}"
    a3 = f"{page_name}의 다음 학습 단계에서는 {a3}"

    return "".join(
        [
            '<section class="faq">',
            f'<article><h3>{escape(q1)}</h3><p>{escape(a1)}</p></article>',
            f'<article><h3>{escape(q2)}</h3><p>{escape(a2)}</p></article>',
            f'<article><h3>{escape(q3)}</h3><p>{escape(a3)}</p></article>',
            '</section>',
        ]
    )
