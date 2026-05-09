"""Core simulation rules for MELTINGPOT, a SPENT-inspired immigrant survival game."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

MAX_WEEKS = 12


@dataclass
class GameState:
    """Mutable player state tracked across the week-by-week simulation."""

    week: int = 1
    cash: int = 720
    health: int = 88
    community: int = 22
    legal: int = 14
    rent_due: int = 275
    food_due: int = 80
    transit_due: int = 35
    legal_fees_paid: int = 0
    authorization_weeks: int = 0
    language_lessons: int = 0
    credential_progress: int = 0
    business_progress: int = 0
    flags: set[str] = field(default_factory=set)
    log: list[str] = field(default_factory=list)

    @property
    def week_costs(self) -> int:
        return self.rent_due + self.food_due + self.transit_due

    @property
    def language_path(self) -> str:
        if self.language_lessons >= 4:
            return "translation confidence"
        if self.language_lessons >= 2:
            return "conversational support"
        return "limited access"

    @property
    def status(self) -> str:
        if self.legal <= 0:
            return "legal crisis"
        if self.legal >= 70 or self.authorization_weeks >= 4:
            return "work authorized"
        if self.legal >= 35:
            return "case pending"
        return "undocumented / waiting"

    @property
    def is_over(self) -> bool:
        return self.week > MAX_WEEKS or self.cash < -350 or self.health <= 0 or self.legal <= 0

    @property
    def ending(self) -> str:
        if self.cash < -350:
            return "You ran out of options and had to rely on emergency housing and informal loans."
        if self.health <= 0:
            return "Health reached zero, causing a medical crisis that ends the season."
        if self.legal <= 0:
            return "Legal stability reached zero, triggering an immigration crisis that ends the season."
        if self.week <= MAX_WEEKS:
            return "The struggle continues."
        score = self.cash + self.legal * 8 + self.community * 6 + self.health * 5
        if score >= 1850:
            return "You finish the season with a fragile foothold and real paths forward."
        if score >= 1250:
            return "You survive the season, but stability still feels one emergency away."
        return "You made it through, but every safety net is thin and costly."

    def clamp(self) -> None:
        self.health = min(100, max(0, self.health))
        self.community = min(100, max(0, self.community))
        self.legal = min(100, max(0, self.legal))

    def record_crisis_consequences(self) -> None:
        if self.health <= 0 and "health_crisis" not in self.flags:
            self.flags.add("health_crisis")
            self.log.append("Health reached zero: a medical crisis ends the season.")
        if self.legal <= 0 and "legal_crisis" not in self.flags:
            self.flags.add("legal_crisis")
            self.log.append("Legal stability reached zero: an immigration crisis ends the season.")

    def apply(self, *, cash: int = 0, health: int = 0, community: int = 0, legal: int = 0,
              language: int = 0, credential: int = 0, business: int = 0, note: str = "") -> None:
        self.cash += cash
        self.health += health
        self.community += community
        self.legal += legal
        self.language_lessons = min(5, self.language_lessons + language)
        self.credential_progress = min(100, self.credential_progress + credential)
        self.business_progress = min(100, self.business_progress + business)
        if note:
            self.log.append(note)
        self.clamp()
        self.record_crisis_consequences()

    def snapshot(self) -> dict[str, int]:
        return {"cash": self.cash, "health": self.health, "community": self.community, "legal": self.legal}

    def finish_week(self) -> None:
        self.cash -= self.week_costs
        self.health -= 3 if self.cash < 100 else 1
        self.community -= 1 if self.cash < 0 else 0
        if self.authorization_weeks:
            self.authorization_weeks += 1
            if self.authorization_weeks >= 4:
                self.legal = max(self.legal, 70)
                self.flags.add("authorized")
        self.week += 1
        self.clamp()
        self.record_crisis_consequences()
        self.log = self.log[-7:]


@dataclass(frozen=True)
class Choice:
    title: str
    description: str
    effect: Callable[[GameState], None]
    requirement: Callable[[GameState], bool] = lambda _state: True


def _under_table(state: GameState) -> None:
    state.apply(cash=360, health=-4, legal=-1, community=-1,
                note="Cash came fast, but the job kept you vulnerable and invisible.")
    if state.week in {3, 8} and state.community < 35:
        state.apply(cash=-70, health=-2, note="A manager shorted your pay because you had little leverage.")


def _wait_authorization(state: GameState) -> None:
    state.authorization_weeks = max(1, state.authorization_weeks)
    state.apply(cash=80, health=-1, legal=10, community=1,
                note="You protected your case, even while paperwork moved slowly.")


def _lawyer(state: GameState) -> None:
    state.legal_fees_paid += 150
    state.apply(cash=-150, health=-1, legal=16,
                note="A lawyer corrected forms and explained deadlines at a painful but manageable price.")


def _stable_job(state: GameState) -> None:
    bonus = 70 if state.language_lessons >= 2 else 0
    state.apply(cash=330 + bonus, health=-3, community=1,
                note="Stable hours helped; language practice made the workplace easier to navigate." if bonus else
                "Stable hours helped, though communication barriers still capped pay.")


def _exploit_job(state: GameState) -> None:
    state.apply(cash=430, health=-7, legal=-2,
                note="The pay was better, but safety rules and overtime promises were ignored.")


def _gig_work(state: GameState) -> None:
    swing = -70 if state.week % 4 == 0 else 60
    state.apply(cash=290 + swing, health=-3,
                note="Gig work gave flexibility, but demand changed without warning.")


def _cheap_housing(state: GameState) -> None:
    state.rent_due = 225
    state.transit_due = 60
    state.apply(cash=25, health=-4, community=1,
                note="Overcrowded housing saved rent but made rest and commuting harder.")


def _safe_housing(state: GameState) -> None:
    denied = state.community < 30 and "cosigner_help" not in state.flags
    if denied:
        state.apply(cash=-30, health=-2, note="A landlord demanded a co-signer you did not have.")
    else:
        state.rent_due = 380
        state.transit_due = 25
        state.apply(health=4, community=2, note="Safer housing improved rest, but rent rose.")


def _study_language(state: GameState) -> None:
    state.apply(cash=-55, health=-1, community=2, language=1,
                note="Language class cost work hours now and unlocked better choices later.")


def _translated_help(state: GameState) -> None:
    state.apply(cash=55, health=4, community=4, legal=2,
                note="With translation confidence, you avoided fees and got clearer answers.")


def _work_extra(state: GameState) -> None:
    state.apply(cash=160, health=-5, community=-2,
                note="Extra hours paid bills while leaving less time for care and relationships.")


def _send_remittance(state: GameState) -> None:
    state.apply(cash=-90, health=-1, community=7,
                note="Money sent home supported family and strengthened your wider safety net.")


def _keep_money(state: GameState) -> None:
    state.apply(health=2, community=-4,
                note="Keeping money reduced immediate danger, but family and community pressure grew.")


def _clinic(state: GameState) -> None:
    discount = 45 if state.community >= 35 else 0
    state.apply(cash=-(80 - discount), health=12, community=2,
                note="A clinic visit helped your health; community knowledge lowered the cost." if discount else
                "A clinic visit helped your health, but the bill still mattered.")


def _avoid_doctor(state: GameState) -> None:
    state.apply(cash=25, health=-7,
                note="Avoiding care saved cash today while making tomorrow more fragile.")


def _network(state: GameState) -> None:
    state.apply(cash=-45, health=2, community=14,
                note="Community ties took time, then produced practical information and backup.")
    if state.community >= 38:
        state.flags.add("cosigner_help")


def _report_exploitation(state: GameState) -> None:
    if state.legal >= 40 or state.community >= 45:
        state.apply(cash=100, health=-2, legal=7, community=3,
                    note="With support, reporting recovered wages and reduced future abuse.")
    else:
        state.apply(cash=-45, health=-6, legal=-3,
                    note="Reporting alone triggered retaliation and frightening visibility.")


def _certification(state: GameState) -> None:
    state.apply(cash=-120, health=-2, community=2, credential=24,
                note="Credential work did not pay today, but your old skills became more legible.")
    if state.credential_progress >= 60:
        state.apply(cash=120, community=2, note="A supervisor finally recognized part of your experience.")


def _small_business(state: GameState) -> None:
    state.apply(cash=-150, health=-2, business=28, community=4,
                note="A tiny business plan risked savings for a path not controlled by one employer.")
    if state.business_progress >= 75:
        state.apply(cash=240, health=2, community=3, note="Your side business began returning steady customers.")


CHOICES: list[Choice] = [
    Choice("Take under-the-table work", "Quick cash, higher legal and exploitation risk.", _under_table),
    Choice("Wait for work authorization", "Slow, safer paperwork path with less income now.", _wait_authorization),
    Choice("Pay immigration lawyer", "Upfront cost for a stronger legal case.", _lawyer),
    Choice("Stable low-wage job", "Predictable hours but limited advancement.", _stable_job),
    Choice("Higher-paying risky job", "More money with safety and wage-theft risks.", _exploit_job),
    Choice("Gig work", "Flexible, unstable income.", _gig_work),
    Choice("Cheap overcrowded apartment", "Lower rent, harder commute and rest.", _cheap_housing),
    Choice("Apply for safer housing", "Higher rent; may require a co-signer or network help.", _safe_housing),
    Choice("Study language", "Lose work hours now to unlock later support.", _study_language),
    Choice("Use translated assistance", "Unlocked by language study; improves paperwork and care.", _translated_help,
           lambda state: state.language_lessons >= 2),
    Choice("Work extra hours", "Immediate cash at health and community cost.", _work_extra),
    Choice("Send remittance", "Support family abroad while tightening your budget.", _send_remittance),
    Choice("Keep money this week", "Reduce immediate risk while straining obligations.", _keep_money),
    Choice("Visit community clinic", "Health improves, cost depends on community knowledge.", _clinic),
    Choice("Avoid doctor", "Save money now; untreated problems grow.", _avoid_doctor),
    Choice("Build community network", "Time away from work for jobs, housing, and emergency support.", _network),
    Choice("Report exploitation", "Seek justice, but risk retaliation without status or support.", _report_exploitation),
    Choice("Pursue certification", "Translate credentials for future mobility.", _certification),
    Choice("Start small business", "Risk savings for independence and long-term upside.", _small_business),
]


EVENTS: tuple[Callable[[GameState], str], ...] = (
    lambda s: _family_emergency(s),
    lambda s: _inspection(s),
    lambda s: _discrimination(s),
    lambda s: _contract_confusion(s),
    lambda s: _community_help(s),
    lambda s: _school_meeting(s),
)


def _family_emergency(state: GameState) -> str:
    state.apply(cash=-75, health=-2, community=5, note="A relative abroad needed emergency help.")
    return "Family emergency abroad: you sent what you could."


def _inspection(state: GameState) -> str:
    if state.legal < 30:
        state.apply(health=-4, legal=-2, note="A workplace inspection made everyone without papers disappear for a day.")
        return "Workplace inspection: hiding cost wages and peace of mind."
    state.apply(health=-1, legal=2, note="Your documents reduced the danger of an inspection.")
    return "Workplace inspection: paperwork helped you stay calm."


def _discrimination(state: GameState) -> str:
    state.apply(cash=-40, health=-2, community=1, note="An application stalled after a name and accent check.")
    return "Name/accent discrimination slowed an opportunity."


def _contract_confusion(state: GameState) -> str:
    if state.language_lessons < 2:
        state.apply(cash=-50, health=-2, note="A contract clause was unclear without translation.")
        return "Contract misunderstanding: missing translation cost money."
    state.apply(health=2, legal=1, note="Language study helped you catch a bad contract clause.")
    return "Contract review: language study prevented a costly mistake."


def _community_help(state: GameState) -> str:
    if state.community >= 30:
        state.apply(cash=85, health=2, community=2, note="A community group shared groceries and a job lead.")
        return "Community support turned relationships into concrete help."
    state.apply(community=1, note="You heard about community support too late to use it this week.")
    return "A support group existed, but you were not connected yet."


def _school_meeting(state: GameState) -> str:
    if state.language_lessons >= 2 or state.community >= 35:
        state.apply(health=2, community=4, note="Translation help made a school/clinic meeting manageable.")
        return "Translation support helped you advocate for family."
    state.apply(health=-3, community=-2, note="A school/clinic meeting went badly without translation.")
    return "No translation: an important meeting left you confused and blamed."


def weekly_event(state: GameState) -> str:
    event = EVENTS[(state.week - 1) % len(EVENTS)]
    return event(state)
