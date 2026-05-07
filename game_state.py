"""Core simulation rules for Crossroads, a SPENT-inspired immigrant survival game."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

MAX_WEEKS = 12


@dataclass
class GameState:
    """Mutable player state tracked across the week-by-week simulation."""

    week: int = 1
    cash: int = 520
    stress: int = 32
    health: int = 82
    english: int = 18
    community: int = 10
    legal: int = 8
    hope: int = 58
    family: int = 55
    rent_due: int = 330
    food_due: int = 95
    transit_due: int = 45
    legal_fees_paid: int = 0
    authorization_weeks: int = 0
    credential_progress: int = 0
    business_progress: int = 0
    flags: set[str] = field(default_factory=set)
    log: list[str] = field(default_factory=list)

    @property
    def week_costs(self) -> int:
        return self.rent_due + self.food_due + self.transit_due

    @property
    def status(self) -> str:
        if self.legal >= 75 or self.authorization_weeks >= 4:
            return "work authorized"
        if self.legal >= 35:
            return "case pending"
        return "undocumented / waiting"

    @property
    def is_over(self) -> bool:
        return self.week > MAX_WEEKS or self.cash < -250 or self.health <= 0 or self.stress >= 100

    @property
    def ending(self) -> str:
        if self.cash < -250:
            return "You could not keep up with debt and were forced into crisis housing."
        if self.health <= 0:
            return "Your health collapsed after too many untreated problems."
        if self.stress >= 100:
            return "Stress became unmanageable, and survival mode took over everything else."
        if self.week <= MAX_WEEKS:
            return "The struggle continues."
        score = self.cash + self.legal * 7 + self.english * 4 + self.community * 4 + self.health * 3 - self.stress * 5
        if score >= 1400:
            return "You finish the season with a fragile foothold and real paths forward."
        if score >= 850:
            return "You survive the season, but stability still feels one emergency away."
        return "You made it through, but every safety net is thin and costly."

    def clamp(self) -> None:
        self.stress = min(100, max(0, self.stress))
        self.health = min(100, max(0, self.health))
        self.english = min(100, max(0, self.english))
        self.community = min(100, max(0, self.community))
        self.legal = min(100, max(0, self.legal))
        self.hope = min(100, max(0, self.hope))
        self.family = min(100, max(0, self.family))

    def apply(self, *, cash: int = 0, stress: int = 0, health: int = 0, english: int = 0,
              community: int = 0, legal: int = 0, hope: int = 0, family: int = 0,
              credential: int = 0, business: int = 0, note: str = "") -> None:
        self.cash += cash
        self.stress += stress
        self.health += health
        self.english += english
        self.community += community
        self.legal += legal
        self.hope += hope
        self.family += family
        self.credential_progress = min(100, self.credential_progress + credential)
        self.business_progress = min(100, self.business_progress + business)
        if note:
            self.log.append(note)
        self.clamp()

    def finish_week(self) -> None:
        self.cash -= self.week_costs
        self.stress += 8 if self.cash < 150 else 3
        self.health -= 5 if self.stress > 75 else 1
        if self.authorization_weeks:
            self.authorization_weeks += 1
            if self.authorization_weeks >= 4:
                self.legal = max(self.legal, 75)
                self.flags.add("authorized")
        self.week += 1
        self.clamp()
        self.log = self.log[-7:]


@dataclass(frozen=True)
class Choice:
    title: str
    description: str
    effect: Callable[[GameState], None]


def _under_table(state: GameState) -> None:
    risk = 16 if state.legal < 35 else 8
    state.apply(cash=430, stress=14, health=-5, legal=-3, hope=-2,
                note=f"Cash came fast, but workplace visibility risk rose by {risk}.")
    if state.week in {3, 8} and state.community < 35:
        state.apply(cash=-160, stress=12, note="A manager withheld pay because you had little leverage.")


def _wait_authorization(state: GameState) -> None:
    state.authorization_weeks = max(1, state.authorization_weeks)
    state.apply(cash=90, stress=4, legal=12, hope=5,
                note="You preserved your case, but savings thinned while paperwork moved slowly.")


def _lawyer(state: GameState) -> None:
    state.legal_fees_paid += 230
    state.apply(cash=-230, stress=5, legal=20, hope=8,
                note="A lawyer corrected forms and explained deadlines, at a painful price.")


def _stable_job(state: GameState) -> None:
    bonus = 90 if state.english >= 45 else 0
    state.apply(cash=340 + bonus, stress=8, health=-2, english=2, hope=2,
                note="Stable hours helped, though language and credential barriers capped pay.")


def _exploit_job(state: GameState) -> None:
    state.apply(cash=520, stress=18, health=-9, hope=-5,
                note="The pay was higher, but safety rules and overtime promises were ignored.")
    if state.legal < 35:
        state.apply(stress=7, legal=-4, note="You stayed quiet about exploitation to avoid exposure.")


def _gig_work(state: GameState) -> None:
    swing = -120 if state.week % 4 == 0 else 80
    state.apply(cash=310 + swing, stress=10, health=-3, community=-1,
                note="Gig work gave flexibility, but demand changed without warning.")


def _cheap_housing(state: GameState) -> None:
    state.rent_due = 240
    state.transit_due = 70
    state.apply(stress=10, health=-4, cash=40,
                note="Overcrowded housing saved rent but raised commute and health strain.")


def _safe_housing(state: GameState) -> None:
    denied = state.community < 30 and "cosigner_help" not in state.flags
    if denied:
        state.apply(cash=-55, stress=10, note="A landlord demanded a co-signer you did not have.")
    else:
        state.rent_due = 430
        state.transit_due = 35
        state.apply(stress=-4, health=3, hope=4, note="Safer housing improved rest, but rent rose.")


def _study_english(state: GameState) -> None:
    state.apply(cash=-80, stress=2, english=14, hope=6,
                note="English class cost work hours now and opened future doors.")


def _work_extra(state: GameState) -> None:
    state.apply(cash=210, stress=12, health=-6, family=-3,
                note="Extra hours paid bills while leaving less time for language and family.")


def _send_remittance(state: GameState) -> None:
    state.apply(cash=-140, stress=3, family=15, hope=3,
                note="Money sent home helped relatives and made this week's budget tighter.")


def _keep_money(state: GameState) -> None:
    state.apply(stress=-2, family=-10, hope=-2,
                note="Keeping money reduced immediate danger, but family pressure grew.")


def _clinic(state: GameState) -> None:
    discount = 55 if state.community >= 35 else 0
    state.apply(cash=-(115 - discount), stress=-3, health=15, community=2,
                note="A clinic visit helped your health; community knowledge lowered the cost." if discount else
                "A clinic visit helped your health, but the bill hurt.")


def _avoid_doctor(state: GameState) -> None:
    state.apply(cash=40, stress=6, health=-12,
                note="Avoiding care saved cash today while making tomorrow more fragile.")


def _network(state: GameState) -> None:
    state.apply(cash=-70, stress=-4, community=16, hope=8,
                note="Community ties took time, then produced practical information and backup.")
    if state.community >= 40:
        state.flags.add("cosigner_help")


def _report_exploitation(state: GameState) -> None:
    if state.legal >= 45 or state.community >= 50:
        state.apply(cash=120, stress=8, legal=8, hope=8,
                    note="With support, reporting recovered wages and reduced future abuse.")
    else:
        state.apply(cash=-80, stress=18, legal=-8, hope=-8,
                    note="Reporting alone triggered retaliation and frightening visibility.")


def _certification(state: GameState) -> None:
    state.apply(cash=-180, stress=6, english=4, credential=22, hope=10,
                note="Credential work did not pay today, but your old skills became more legible.")
    if state.credential_progress >= 60:
        state.apply(cash=110, hope=5, note="A supervisor finally recognized part of your experience.")


def _small_business(state: GameState) -> None:
    state.apply(cash=-220, stress=7, business=25, community=4, hope=10,
                note="A tiny business plan risked savings for a path not controlled by one employer.")
    if state.business_progress >= 75:
        state.apply(cash=260, stress=-3, hope=8, note="Your side business began returning steady customers.")


CHOICES: list[Choice] = [
    Choice("Take under-the-table work", "Quick cash, higher legal and exploitation risk.", _under_table),
    Choice("Wait for work authorization", "Slow, safer paperwork path with less income now.", _wait_authorization),
    Choice("Pay immigration lawyer", "Large upfront cost for a stronger legal case.", _lawyer),
    Choice("Stable low-wage job", "Predictable hours but limited advancement.", _stable_job),
    Choice("Higher-paying risky job", "More money with safety and wage-theft risks.", _exploit_job),
    Choice("Gig work", "Flexible, unstable income.", _gig_work),
    Choice("Cheap overcrowded apartment", "Lower rent, worse commute and health conditions.", _cheap_housing),
    Choice("Apply for safer housing", "Higher rent; may require a co-signer or network help.", _safe_housing),
    Choice("Study English", "Lose work hours now for long-term access.", _study_english),
    Choice("Work extra hours", "Immediate cash at health and family cost.", _work_extra),
    Choice("Send remittance", "Support family abroad while tightening your budget.", _send_remittance),
    Choice("Keep money this week", "Reduce immediate risk while straining family obligations.", _keep_money),
    Choice("Visit community clinic", "Health improves, cost depends on community knowledge.", _clinic),
    Choice("Avoid doctor", "Save money now; untreated problems grow.", _avoid_doctor),
    Choice("Build community network", "Time away from work for job, housing, and emergency support.", _network),
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
    state.apply(cash=-120, stress=8, family=8, note="A relative abroad needed emergency help.")
    return "Family emergency abroad: you sent what you could."


def _inspection(state: GameState) -> str:
    if state.legal < 30:
        state.apply(stress=14, legal=-5, hope=-4, note="A workplace inspection made everyone without papers disappear for a day.")
        return "Workplace inspection: hiding cost wages and peace of mind."
    state.apply(stress=4, legal=2, note="Your documents reduced the danger of an inspection.")
    return "Workplace inspection: paperwork helped you stay calm."


def _discrimination(state: GameState) -> str:
    state.apply(cash=-70, stress=7, hope=-3, note="An application stalled after a name and accent check.")
    return "Name/accent discrimination slowed an opportunity."


def _contract_confusion(state: GameState) -> str:
    if state.english < 40:
        state.apply(cash=-95, stress=8, note="A contract clause was unclear without translation.")
        return "Contract misunderstanding: missing translation cost money."
    state.apply(english=2, hope=3, note="English practice helped you catch a bad contract clause.")
    return "Contract review: language study prevented a costly mistake."


def _community_help(state: GameState) -> str:
    if state.community >= 30:
        state.apply(cash=110, stress=-5, hope=6, note="A community group shared groceries and a job lead.")
        return "Community support turned relationships into concrete help."
    state.apply(stress=3, note="You heard about community support too late to use it this week.")
    return "A support group existed, but you were not connected yet."


def _school_meeting(state: GameState) -> str:
    if state.english >= 35 or state.community >= 35:
        state.apply(stress=-2, family=5, hope=4, note="Translation help made a school/clinic meeting manageable.")
        return "Translation support helped you advocate for family."
    state.apply(stress=9, family=-5, note="A school/clinic meeting went badly without translation.")
    return "No translation: an important meeting left you confused and blamed."


def weekly_event(state: GameState) -> str:
    event = EVENTS[(state.week - 1) % len(EVENTS)]
    return event(state)
