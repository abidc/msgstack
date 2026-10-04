"""Seed script for MsgStack with 10 complete message houses."""

from datetime import datetime
from uuid import uuid4

from src.models import Channel, HouseStatus, KeyMessage, MessageHouse, Persona, SectionType
from src.store import Store


def seed():
    """Seed the database with 10 complete message houses."""
    store = Store("msgstack.db")
    store.init()

    now = datetime.utcnow()
    houses_data = [
        _acme_cloud_security(now),
        _helix_hr(now),
        _apex_financial_analytics(now),
        _clarity_cms(now),
        _forge_devops(now),
        _nexus_supply_chain(now),
        _pulse_customer_success(now),
        _solara_energy_management(now),
        _vantage_sales_intelligence(now),
        _atlas_knowledge_management(now),
    ]

    total_messages = 0
    total_personas = 0

    for house_data in houses_data:
        house = house_data["house"]
        store.upsert_house(house)

        for msg in house_data["messages"]:
            store.upsert_key_message(msg)
            total_messages += 1

        for persona in house_data["personas"]:
            store.upsert_persona(persona)
            total_personas += 1

    return len(houses_data)


def _acme_cloud_security(now):
    house_id = uuid4()
    house = MessageHouse(
        id=house_id,
        name="Acme Cloud Security Platform",
        source="seed",
        summary="Enterprise-grade cybersecurity platform for mid-market companies. AI-powered threat detection, zero-trust architecture, and compliance automation.",
        audience="Mid-market enterprises, 200-2000 employees",
        brand_personality="Security-first, precise, trustworthy",
        positioning="The cybersecurity platform that thinks like an attacker. Acme uses AI to predict threats before they happen, saving mid-market companies an average of $2.3M in breach costs.",
        tagline="Predict threats. Prevent breaches.",
        differentiation="AI-native threat prediction vs reactive legacy firewalls. 3-minute deployment vs weeks-long implementations.",
        status=HouseStatus.ACTIVE,
        last_synced=now,
    )

    messages = [
        # Headlines (3)
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=1, content="Your firewall can't think. Acme can.", variants={"linkedin": "Still playing whack-a-mole with threats? Acme predicts them before they strike.", "email": "Stop reacting. Start predicting.", "paid": "Think like a hacker. Stop like a pro."}, personas=["CISO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=2, content="$2.3M: The average breach cost we help mid-market companies avoid.", variants={"linkedin": "What would $2.3M mean to your bottom line? We help you never find out.", "email": "The $2.3M question every board should ask", "paid": "Save $2.3M on average"}, personas=["CFO", "CISO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=3, content="Security without the enterprise price tag.", variants={"linkedin": "Enterprise-grade security. Mid-market pricing.", "email": "Finally, enterprise security that fits your budget", "paid": "Big security. Right size."}, personas=["IT Director"], channels=[Channel.ALL]),
        # Subheads (3)
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=1, content="AI that predicts attacks 48 hours before they happen — not after they're inside.", variants={"linkedin": "48 hours of warning. That is the difference between a near-miss and a headline.", "email": "48 hours of warning before breach"}, personas=["CISO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=2, content="Zero-trust architecture deployed in 3 minutes, not 3 months.", variants={"linkedin": "Zero-trust shouldn't take zero-time to deploy.", "email": "Deploy zero-trust in 3 minutes"}, personas=["IT Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=3, content="SOC 2, HIPAA, PCI-DSS compliant out of the box.", variants={"linkedin": "Compliance is table stakes. We give you it straight.", "email": "Compliance built in, not bolted on"}, personas=["Compliance Officer"], channels=[Channel.ALL]),
        # Benefits (4)
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=1, content="AI threat prediction catches 94% of attacks before they execute.", variants={"linkedin": "94% of attacks stopped before they do damage.", "email": "94% threat detection rate"}, personas=["CISO", "IT Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=2, content="Reduce security alerts by 73% with intelligent triage.", variants={"linkedin": "73% less alert fatigue. 100% more sleep.", "email": "Cut alerts by 73%"}, personas=["IT Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=3, content="Average 4-hour onboarding vs industry standard 6 weeks.", variants={"linkedin": "In the time you read this, you could be protected.", "email": "Protected in 4 hours"}, personas=["CISO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=4, content="$890/month flat — no per-seat fees, no surprises.", variants={"linkedin": "Predictable cost. Predictable protection.", "email": "One price. No seat math.", "paid": "From $890/mo"}, personas=["CFO"], channels=[Channel.ALL]),
        # Proof Points (3)
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=1, content="487 mid-market companies protected; zero breaches in 18 months.", variants={"linkedin": "487 companies. 0 breaches. 18 months.", "email": "0 breaches across 487 companies"}, personas=["CISO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=2, content="$2.3M average avoided breach costs per protected company.", variants={"linkedin": "That's not a typo. $2.3M saved.", "email": "$2.3M average savings"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=3, content="Named G2 Leader in Cloud Security for mid-market, Q1 2026.", variants={"linkedin": "G2 validates what our customers tell us.", "email": "G2 Leader in Cloud Security"}, personas=["CISO"], channels=[Channel.ALL]),
        # Objections (3)
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=1, content="We already have a firewall.", variants={"linkedin": "Firewalls stop known threats. We stop unknown ones.", "email": "Firewalls: known threats. Acme: unknown threats"}, personas=["IT Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=2, content="We don't have a security team to manage it.", variants={"linkedin": "That's the point. Acme runs itself.", "email": "No security team needed"}, personas=["IT Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=3, content="It's too expensive for our size.", variants={"linkedin": "The cost of a breach is the same regardless of your size. So's the protection.", "email": "Right-sized pricing for right-sized security"}, personas=["CFO"], channels=[Channel.ALL]),
        # Social Proof (3)
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=1, content="Recommended by the CISOs of 3 Fortune 500 alumni at mid-market companies.", variants={"linkedin": "When Fortune 500 CISOs go smaller, they go Acme.", "email": "Fortune 500-tested, mid-market built"}, personas=["CISO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=2, content="G2 Crowd: 4.8/5 stars from 124 verified reviews.", variants={"linkedin": "124 security leaders. 4.8 stars.", "email": "4.8/5 from 124 reviews"}, personas=["IT Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=3, content="\"Implementation was done before we finished our coffee.\" — VP Security, TechScale Inc", variants={"linkedin": "Fastest deployment in security, bar none.", "email": "\"Done before our coffee was cold.\""}, personas=["IT Director"], channels=[Channel.ALL]),
        # Positioning (1)
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.POSITIONING, priority=1, content="AI-native cybersecurity for mid-market enterprises who need Fortune 500 protection without the Fortune 500 budget.", variants={"linkedin": "Fortune 500 protection. Mid-market price. No compromise.", "email": "Enterprise security. Mid-market price."}, personas=["CISO"], channels=[Channel.ALL]),
    ]

    personas = [
        Persona(id=uuid4(), message_house_id=house_id, name="CISO", description="Chief Information Security Officer. Owns security strategy and reports to CEO.", pain_points=["Alert fatigue from too many tools", "Board doesn't understand security risk", "Breach costs are existential"], buying_triggers=["Board mandate", "Near-miss incident", "Compliance deadline"], objections=["We have legacy tools", "No team to manage", "Can't afford enterprise solutions"]),
        Persona(id=uuid4(), message_house_id=house_id, name="IT Director", description="Manages IT infrastructure and security tools. Hands-on with deployments.", pain_points=["Tool sprawl", "Complex implementations", "False positives"], buying_triggers=["Ease of deployment", "Integration with existing stack", "Vendor reliability"], objections=["We have a firewall", "Too complex", "Not enough staff"]),
        Persona(id=uuid4(), message_house_id=house_id, name="Compliance Officer", description="Ensures organization meets regulatory requirements.", pain_points=["Manual compliance audits", "Audit prep time", "Changing regulations"], buying_triggers=["Upcoming audit", "New regulation", "Board pressure"], objections=["Does it meet all requirements", "Audit trail", "Reporting capability"]),
    ]

    return {"house": house, "messages": messages, "personas": personas}


def _helix_hr(now):
    house_id = uuid4()
    house = MessageHouse(
        id=house_id,
        name="Helix HR",
        source="seed",
        summary="AI-powered HR platform for scaling startups. Automate onboarding, performance reviews, and compensation decisions.",
        audience="Scaling startups, 50-500 employees",
        brand_personality="Modern, helpful, efficient",
        positioning="Helix lets scaling teams hire faster, manage performance smarter, and pay fairly. AI that handles the admin so you can focus on the people.",
        tagline="HR that scales with you.",
        differentiation="Purpose-built for 50-500 vs legacy HR systems built for enterprises. AI-native from day one.",
        status=HouseStatus.ACTIVE,
        last_synced=now,
    )

    messages = [
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=1, content="Stop managing HR. Start leading your people.", variants={"linkedin": "HR admin is theft. Get your time back.", "email": "Your time > HR paperwork"}, personas=["CPO", "HR Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=2, content="Hire faster. Pay fairly. Scale smarter.", variants={"linkedin": "Three things startups need Helix to do.", "email": "Hire. Pay. Scale."}, personas=["CPO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=3, content="From 50 to 500 without the HR bottleneck.", variants={"linkedin": "Growth without the growing pains.", "email": "Scale without the bottleneck"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=1, content="Onboarding in minutes, not days. Paperwork that fills itself.", variants={"linkedin": "Onboarding: done in minutes, not days.", "email": "Minutes, not days"}, personas=["HR Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=2, content="AI-compensation insights that eliminate pay gaps before they start.", variants={"linkedin": "Pay equity, built in.", "email": "Pay gaps: prevent, not just find"}, personas=["CPO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=3, content="Performance reviews that actually improve performance.", variants={"linkedin": "Reviews that work.", "email": "Reviews that help"}, personas=["HR Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=1, content="Cut onboarding time by 85% with automated workflows.", variants={"linkedin": "85% less onboarding time.", "email": "85% time savings"}, personas=["HR Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=2, content="Real-time compensation benchmarks across 10,000+ startup salaries.", variants={"linkedin": "Data-backed pay decisions.", "email": "10,000+ salary benchmark"}, personas=["CPO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=3, content="Reduce HR admin time by 12 hours/week per 100 employees.", variants={"linkedin": "12 hours/week recovered.", "email": "12 hours/week back"}, personas=["HR Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=4, content="Everything in one platform. No more tool hopping.", variants={"linkedin": "One platform. No hopping.", "email": "One platform for all HR"}, personas=["CPO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=1, content="340+ startups scaled from 50 to 500+ with Helix.", variants={"linkedin": "340 startups grew up with Helix.", "email": "340+ scaling startups"}, personas=["CPO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=2, content="4.9/5 G2 rating from 89 HR leaders.", variants={"linkedin": "89 HR leaders. 4.9 stars.", "email": "4.9/5 rating"}, personas=["HR Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=3, content="Average 2-day implementation vs 8-week industry average.", variants={"linkedin": "2 days implemented. 8 weeks is average.", "email": "2 days vs 8 weeks"}, personas=["CPO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=1, content="We already use several HR tools.", variants={"linkedin": "Replace 5 tools with 1.", "email": "Replace 5 with 1"}, personas=["HR Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=2, content="Our team is too small for HR tech.", variants={"linkedin": "Right-sized for when small gets big.", "email": "Built for your size"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=3, content="I don't trust AI with HR decisions.", variants={"linkedin": "AI recommends. You decide.", "email": "AI insight, you authority"}, personas=["CPO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=1, content="Used by 5 YC unicorns this batch.", variants={"linkedin": "YC trusts Helix.", "email": "5 YC unicorns"}, personas=["CPO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=2, content="\"Best HR investment we've made.\" — Ops Lead, Series B fintech", variants={"linkedin": "HR that actually helps.", "email": "\"Best HR investment\""}, personas=["HR Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=3, content="Featured in TechCrunch, Forbes, and HR Brew.", variants={"linkedin": "Press doesn't lie.", "email": "TechCrunch: Helix"}, personas=["CPO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.POSITIONING, priority=1, content="AI-powered HR for startups that want to scale without the growing pains.", variants={"linkedin": "Scale without the pain.", "email": "HR that scales"}, personas=["CPO"], channels=[Channel.ALL]),
    ]

    personas = [
        Persona(id=uuid4(), message_house_id=house_id, name="CPO", description="Chief People Officer. Owns HR strategy and hiring.", pain_points=["Hiring fast enough", "Pay equity", "Scaling culture"], buying_triggers=["Series round", "Leadership hire", "Retention issue"], objections=["Too many tools", "Trust AI", "Cost"]),
        Persona(id=uuid4(), message_house_id=house_id, name="HR Manager", description="Hands-on HR lead. Handles day-to-day operations.", pain_points=["Admin overload", "Tool juggling", "Manual processes"], buying_triggers=["Growth milestone", "Team feedback", "Compliance need"], objections=["Too complex", "Integration", "Onboarding time"]),
        Persona(id=uuid4(), message_house_id=house_id, name="CFO", description="Finance lead. Concerned about cost and ROI.", pain_points=["HR tool costs", "Unpredictable spend", "Hidden fees"], buying_triggers=["Budget planning", "Board request", "Scaling"], objections=["Too expensive", "Unclear ROI", "Per-seat pricing"]),
    ]

    return {"house": house, "messages": messages, "personas": personas}


def _apex_financial_analytics(now):
    house_id = uuid4()
    house = MessageHouse(
        id=house_id,
        name="Apex Financial Analytics",
        source="seed",
        summary="Real-time business intelligence for fintech and financial services. Instant insights from messy financial data.",
        audience="Fintech startups, financial services firms, 100-2000 employees",
        brand_personality="Precise, data-driven, authoritative",
        positioning="Apex transforms raw financial chaos into board-ready insights in seconds. No data team required. No spreadsheets required. Just answers.",
        tagline="Financial answers at the speed of thought.",
        differentiation="Instant query response vs wait-hours dashboard building. Works with messy data vs requiring clean data first.",
        status=HouseStatus.ACTIVE,
        last_synced=now,
    )

    messages = [
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=1, content="Ask questions. Get answers. No SQL required.", variants={"linkedin": "Ask your data anything.", "email": "Answers, not dashboards"}, personas=["CFO", "VP Finance"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=2, content="Board-ready insights in 30 seconds, not 30 hours.", variants={"linkedin": "30 seconds to board-ready.", "email": "30 seconds not 30 hours"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=3, content="Your financial data finally makes sense.", variants={"linkedin": "Financial clarity, at last.", "email": "Data that makes sense"}, personas=["Data Analyst"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=1, content="Connects to QuickBooks, Xero, NetSuite, and 40+ more. Messy data welcome.", variants={"linkedin": "Any data source. Any mess. Answer ready.", "email": "40+ integrations"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=2, content="Natural language queries. \"What's our burn rate by cohort?\" Done.", variants={"linkedin": "Ask in plain English.", "email": "Plain English queries"}, personas=["VP Finance"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=3, content="Real-time anomaly detection before problems compound.", variants={"linkedin": "Find problems before they find you.", "email": "Problem detection"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=1, content="Cut financial reporting time by 90%.", variants={"linkedin": "90% faster reporting.", "email": "90% time saved"}, personas=["VP Finance"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=2, content="Zero data engineering required.", variants={"linkedin": "No engineers needed.", "email": "No engineering required"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=3, content="Updates every 15 minutes, not daily.", variants={"linkedin": "15-minute updates.", "email": "Real-time updates"}, personas=["Data Analyst"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=4, content="From 3-day close to 3-hour close.", variants={"linkedin": "3-hour close.", "email": "Close in 3 hours"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=1, content="227 fintechs trust Apex for financial clarity.", variants={"linkedin": "227 fintechs can't be wrong.", "email": "227 fintech companies"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=2, content="#1 finance product on Product Hunt 2025.", variants={"linkedin": "Product Hunt #1.", "email": "#1 on Product Hunt"}, personas=["VP Finance"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=3, content="$4.2B ARR analyzed monthly on platform.", variants={"linkedin": "$4.2B analyzed monthly.", "email": "$4.2B monthly"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=1, content="We already have Looker.", variants={"linkedin": "Faster than Looker. Simpler than Looker.", "email": "Looker, but faster"}, personas=["Data Analyst"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=2, content="Our data is too messy.", variants={"linkedin": "Messy data is our specialty.", "email": "We love messy data"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=3, content="We need SQL for complex queries.", variants={"linkedin": "We'll generate the SQL.", "email": "We write the SQL"}, personas=["Data Analyst"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=1, content="Used by 12 Stripe-funded fintechs.", variants={"linkedin": "Stripe-backed trust.", "email": "12 Stripe companies"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=2, content="\"Finally, finance that finance people can use.\" — CFO, Fintech unicorn", variants={"linkedin": "Finance teams love Apex.", "email": "\"Finance that works\""}, personas=["VP Finance"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=3, content="G2 Leader in Financial Analytics, Q1 2026.", variants={"linkedin": "G2 validated.", "email": "G2 Leader"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.POSITIONING, priority=1, content="AI-powered financial intelligence for fintech who need answers, not dashboards.", variants={"linkedin": "Answers, not dashboards.", "email": "Answers, not dashboards"}, personas=["CFO"], channels=[Channel.ALL]),
    ]

    personas = [
        Persona(id=uuid4(), message_house_id=house_id, name="CFO", description="Chief Financial Officer. Owns financial strategy and reporting.", pain_points=["Slow close", "Messy data", "Board requests"], buying_triggers=["Board meeting", "Fundraise", "Audit"], objections=["Integration", "Too expensive", "Data quality"]),
        Persona(id=uuid4(), message_house_id=house_id, name="Data Analyst", description="Hands-on financial analyst. Builds reports.", pain_points=["Dashboard building", "Ad-hoc requests", "Data cleaning"], buying_triggers=["Self-serve need", "Efficiency mandate"], objections=["Complexity", "SQL requirement"]),
        Persona(id=uuid4(), message_house_id=house_id, name="VP Finance", description="VP of Finance. Owns financial operations.", pain_points=["Team capacity", "Reporting delays", "Multiple tools"], buying_triggers=["Scaling", "Visibility need"], objections=["Dashboard features", "Data freshness"]),
    ]

    return {"house": house, "messages": messages, "personas": personas}


def _clarity_cms(now):
    house_id = uuid4()
    house = MessageHouse(
        id=house_id,
        name="Clarity CMS",
        source="seed",
        summary="Headless CMS for enterprise content teams. API-first, developer-friendly, marketer-approved.",
        audience="Enterprise marketing teams, 500+ employees",
        brand_personality="Clean, powerful, flexible",
        positioning="Clarity gives developers the API flexibility they want and marketers the editing experience they love. The CMS that doesn't slow anyone down.",
        tagline="Content without the friction.",
        differentiation="Headless-first vs add-on headless. 50+ native integrations vs requiring middleware. Real-time preview vs save-and-pray.",
        status=HouseStatus.ACTIVE,
        last_synced=now,
    )

    messages = [
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=1, content="Your content deserves better than a clunky CMS.", variants={"linkedin": "Ditch the clunky CMS.", "email": "Content without the pain"}, personas=["VP Marketing", "CTO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=2, content="API-first CMS that developers actually like.", variants={"linkedin": "Developers: you'll actually like this.", "email": "CMS developers love"}, personas=["CTO", "Content Strategist"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=3, content="Content at the speed of your team.", variants={"linkedin": "Keep up with your content.", "email": "Content at speed"}, personas=["VP Marketing"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=1, content="50+ native integrations: Next.js, Hugo, Contentful migration, and more.", variants={"linkedin": "50+ integrations, built in.", "email": "50+ integrations"}, personas=["CTO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=2, content="Real-time preview. No more save-and-pray.", variants={"linkedin": "Preview before publish.", "email": "Real-time preview"}, personas=["Content Strategist"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=3, content="Structured content for unstructured channels.", variants={"linkedin": "Content goes everywhere.", "email": "Content everywhere"}, personas=["VP Marketing"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=1, content="Migrate from Contentful in 2 clicks.", variants={"linkedin": "2-click migration from Contentful.", "email": "2-click migration"}, personas=["CTO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=2, content="Decoupled content, unified workflow.", variants={"linkedin": "Decoupled content.", "email": "Decoupled, unified"}, personas=["VP Marketing"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=3, content="Git-like versioning for content.", variants={"linkedin": "Git for content.", "email": "Git for content"}, personas=["Content Strategist"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=4, content="Instant API response <50ms.", variants={"linkedin": "Sub-50ms API.", "email": "Sub-50ms response"}, personas=["CTO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=1, content="87 enterprise content teams on Clarity.", variants={"linkedin": "87 enterprise teams.", "email": "87 enterprise teams"}, personas=["VP Marketing"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=2, content="1.2M content items served daily.", variants={"linkedin": "1.2M items daily.", "email": "1.2M daily"}, personas=["CTO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=3, content="4.7/5 G2 from 156 marketing leaders.", variants={"linkedin": "156 leaders. 4.7 stars.", "email": "4.7/5 rating"}, personas=["Content Strategist"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=1, content="We're locked into Contentful.", variants={"linkedin": "2-click migration changes that.", "email": "Simple migration"}, personas=["CTO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=2, content="Headless is too technical for our team.", variants={"linkedin": "We make headless easy.", "email": "Headless made easy"}, personas=["VP Marketing"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=3, content="We need enterprise SLA.", variants={"linkedin": "99.99% uptime SLA.", "email": "Enterprise SLA"}, personas=["CTO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=1, content="3 Fortune 500 marketing teams.", variants={"linkedin": "Fortune 500 trust.", "email": "3 Fortune 500s"}, personas=["VP Marketing"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=2, content="\"The CMS we should've had years ago.\" — Dir Content, EnterpriseCo", variants={"linkedin": "Finally, a CMS that works.", "email": "\"Should've had years ago\""}, personas=["Content Strategist"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=3, content="Featured in M arketo blog and Content Marketing Institute.", variants={"linkedin": "Industry recognized.", "email": "Industry validated"}, personas=["VP Marketing"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.POSITIONING, priority=1, content="Headless CMS for enterprise teams who want speed without the pain.", variants={"linkedin": "Fast content. Happy teams.", "email": "Fast content"}, personas=["CTO"], channels=[Channel.ALL]),
    ]

    personas = [
        Persona(id=uuid4(), message_house_id=house_id, name="VP Marketing", description="VP of Marketing. Owns content strategy and execution.", pain_points=["Slow content ops", "Multiple systems", "Developer bottlenecks"], buying_triggers=["Website redesign", "Martech consolidation"], objections=["Enterprise features", "Security"]),
        Persona(id=uuid4(), message_house_id=house_id, name="Content Strategist", description="Owns content architecture and editorial workflow.", pain_points=["Workflow friction", "Preview limitations", "Versioning"], buying_triggers=["Workflow improvement", "Content scale"], objections=["Learning curve", "Integration"]),
        Persona(id=uuid4(), message_house_id=house_id, name="CTO", description="Technical lead. Evaluates CMS for engineering fit.", pain_points=["API flexibility", "Integration complexity", "Performance"], buying_triggers=["Tech refresh", "Performance issues"], objections=["Headless complexity", "Enterprise SLA"]),
    ]

    return {"house": house, "messages": messages, "personas": personas}


def _forge_devops(now):
    house_id = uuid4()
    house = MessageHouse(
        id=house_id,
        name="Forge DevOps",
        source="seed",
        summary="The developer platform that actually improves developer experience. CI/CD, feature flags, and observability in one.",
        audience="Engineering teams, 20-500 developers",
        brand_personality="Developer-centric, fast, reliable",
        positioning="Forge removes the ops from DevOps. CI/CD, feature flags, and observability that developers actually enjoy using.",
        tagline="DevOps that developers love.",
        differentiation="Developer-first UX vs ops-first legacy tools. Single platform vs tool sprawl. Built on Rust vs Java legacy.",
        status=HouseStatus.ACTIVE,
        last_synced=now,
    )

    messages = [
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=1, content="CI/CD that doesn't feel like a tax.", variants={"linkedin": "CI/CD you won't hate.", "email": "CI/CD that doesn't hurt"}, personas=["Engineering Manager", "Staff Engineer"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=2, content="One platform. Zero friction.", variants={"linkedin": "One platform. Zero friction.", "email": "One platform"}, personas=["CTO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=3, content="Ship faster. Break less. Sleep more.", variants={"linkedin": "Ship fast. Sleep well.", "email": "Ship and sleep"}, personas=["Engineering Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=1, content="3-minute setup. Not 3 days.", variants={"linkedin": "3 minutes, not 3 days.", "email": "3 minutes setup"}, personas=["Staff Engineer"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=2, content="Feature flags shipped directly from merge. No rollout required.", variants={"linkedin": "Flags from merge.", "email": "Flags at merge"}, personas=["Engineering Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=3, content="Observability that tells you what matters.", variants={"linkedin": "Alerts that help.", "email": "Alerts that help"}, personas=["Staff Engineer"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=1, content="2x faster deploys on average.", variants={"linkedin": "2x faster deploys.", "email": "2x faster"}, personas=["CTO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=2, content="Cut incident MTTR by 60%.", variants={"linkedin": "60% faster recovery.", "email": "60% MTTR reduction"}, personas=["Staff Engineer"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=3, content="Replace Jenkins + LaunchDarkly + Datadog. One platform.", variants={"linkedin": "3 tools. 1 platform.", "email": "Replace 3 tools"}, personas=["Engineering Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=4, content="No configuration required until you need it.", variants={"linkedin": "Defaults that work.", "email": "Smart defaults"}, personas=["Staff Engineer"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=1, content="1,200 engineering teams ship with Forge.", variants={"linkedin": "1,200 teams.", "email": "1,200 teams"}, personas=["CTO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=2, content="15M+ deploys this year.", variants={"linkedin": "15M deploys.", "email": "15M deploys"}, personas=["Engineering Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=3, content="4.9/5 DevTools review.", variants={"linkedin": "Developer loved.", "email": "4.9/5"}, personas=["Staff Engineer"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=1, content="We already use Jenkins.", variants={"linkedin": "Jenkins is legacy. Forge is future.", "email": "Past vs future"}, personas=["Staff Engineer"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=2, content="Too expensive for our team.", variants={"linkedin": "Replace 3 tools for less.", "email": "Less than 3 tools"}, personas=["CTO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=3, content="We need enterprise support.", variants={"linkedin": "24/7 enterprise support.", "email": "Enterprise support"}, personas=["CTO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=1, content="Used by 8 unicorn engineering teams.", variants={"linkedin": "Unicorn approved.", "email": "8 unicorns"}, personas=["CTO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=2, content="\"Forge is what Jenkins should've been.\" — Staff Eng, Crypto unicorn", variants={"linkedin": "The Jenkins upgrade.", "email": "\"Should've been\""}, personas=["Staff Engineer"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=3, content="Hacker News front page 3 times.", variants={"linkedin": "HN loved.", "email": "3x HN front page"}, personas=["Engineering Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.POSITIONING, priority=1, content="Developer platform that developers actually enjoy.", variants={"linkedin": "Devs love it.", "email": "Devs love it"}, personas=["CTO"], channels=[Channel.ALL]),
    ]

    personas = [
        Persona(id=uuid4(), message_house_id=house_id, name="Engineering Manager", description="Manages engineering team and delivery.", pain_points=["Deployment delays", "Tool switching", "Incident response"], buying_triggers=["Velocity goals", "DevEx improvement"], objections=["Cost", "Migration effort"]),
        Persona(id=uuid4(), message_house_id=house_id, name="Staff Engineer", description="Principal engineer. Owns technical decisions.", pain_points=["Jenkins pain", "Manual deploys", "Alert fatigue"], buying_triggers=["Tech refresh", "Developer experience"], objections=["Complexity", "Learning curve"]),
        Persona(id=uuid4(), message_house_id=house_id, name="CTO", description="Technical leadership. Owns engineering strategy.", pain_points=["Tool sprawl", "Security", "Cost visibility"], buying_triggers=["Platform consolidation", "Metrics"], objections=["Enterprise support", "Pricing"]),
    ]

    return {"house": house, "messages": messages, "personas": personas}


def _nexus_supply_chain(now):
    house_id = uuid4()
    house = MessageHouse(
        id=house_id,
        name="Nexus Supply Chain",
        source="seed",
        summary="AI supply chain optimization for enterprise. Predict demand, reduce waste, and optimize inventory in real-time.",
        audience="Manufacturing, retail, CPG companies with $50M+ revenue",
        brand_personality="Strategic, data-driven, proven",
        positioning="Nexus predicts supply chain disruptions before they hit. AI that turns your supply chain from a cost center into a competitive advantage.",
        tagline="Supply chain, predicted.",
        differentiation="AI-native prediction vs spreadsheet forecasting. Real-time optimization vs monthly reviews. 94% accuracy vs 70% industry average.",
        status=HouseStatus.ACTIVE,
        last_synced=now,
    )

    messages = [
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=1, content="Your next supply chain disruption? Nexus sees it coming.", variants={"linkedin": "See disruptions before they hit.", "email": "See it coming"}, personas=["VP Operations"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=2, content="Turn your supply chain into a moat, not a vulnerability.", variants={"linkedin": "Supply chain as advantage.", "email": "Supply chain advantage"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=3, content="What if you could see tomorrow's problems today?", variants={"linkedin": "See tomorrow today.", "email": "Tomorrow today"}, personas=["Supply Chain Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=1, content="94% demand forecast accuracy. 2x the industry average.", variants={"linkedin": "94% accuracy.", "email": "94% accuracy"}, personas=["VP Operations"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=2, content="Reduce inventory waste by 31% automatically.", variants={"linkedin": "31% less waste.", "email": "31% waste reduction"}, personas=["Supply Chain Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=3, content="Real-time optimization, not monthly reviews.", variants={"linkedin": "Real-time, not monthly.", "email": "Real-time optimization"}, personas=["VP Operations"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=1, content="Cut stockouts by 67% before they happen.", variants={"linkedin": "67% fewer stockouts.", "email": "67% stockout reduction"}, personas=["Supply Chain Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=2, content="Reduce working capital tied to inventory by 18%.", variants={"linkedin": "18% less working capital.", "email": "18% capital freed"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=3, content="One platform connects suppliers, warehouses, and retailers.", variants={"linkedin": "One platform. End to end.", "email": "End-to-end"}, personas=["VP Operations"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=4, content="Integrates with SAP, Oracle, and NetSuite in days.", variants={"linkedin": "We integrate in days.", "email": "Days, not months"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=1, content="$2.1B in supply chain decisions optimized monthly.", variants={"linkedin": "$2.1B optimized.", "email": "$2.1B optimized"}, personas=["VP Operations"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=2, content="Used by 156 manufacturing and retail companies.", variants={"linkedin": "156 supply chains.", "email": "156 companies"}, personas=["Supply Chain Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=3, content="Gartner Cool Vendor 2025.", variants={"linkedin": "Gartner validated.", "email": "Gartner Cool Vendor"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=1, content="We already have SAP.", variants={"linkedin": "We enhance SAP.", "email": "SAP enhancement"}, personas=["VP Operations"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=2, content="Our data is too messy for AI.", variants={"linkedin": "We handle messy supply chain data.", "email": "Messy data is our know-how"}, personas=["Supply Chain Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=3, content="Implementation takes too long.", variants={"linkedin": "Days, not months.", "email": "Days not months"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=1, content="3 Fortune 500 supply chains.", variants={"linkedin": "Fortune 500 trust.", "email": "3 Fortune 500s"}, personas=["VP Operations"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=2, content="\"Nexus found a problem we'd have missed until Q4.\" — Supply Dir, AutoParts Inc", variants={"linkedin": "Catches what you'd miss.", "email": "\"Caught the problem\""}, personas=["Supply Chain Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=3, content="Supply Chain Digest recommendation Q1 2026.", variants={"linkedin": "Industry validated.", "email": "Supply Chain Digest"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.POSITIONING, priority=1, content="AI that turns supply chain into competitive advantage.", variants={"linkedin": "Supply chain competitive edge.", "email": "Competitive edge"}, personas=["VP Operations"], channels=[Channel.ALL]),
    ]

    personas = [
        Persona(id=uuid4(), message_house_id=house_id, name="VP Operations", description="VP of Operations. Owns supply chain strategy.", pain_points=["Disruptions", "Waste", "Forecasting errors"], buying_triggers=["Cost reduction", "Risk management"], objections=["Integration", "Data quality"]),
        Persona(id=uuid4(), message_house_id=house_id, name="Supply Chain Manager", description="Day-to-day supply chain management.", pain_points=["Stockouts", "Manual planning", "Supplier complexity"], buying_triggers=["Automation need", "Accuracy goals"], objections=["Migration", "Time"]),
        Persona(id=uuid4(), message_house_id=house_id, name="CFO", description="Finance lead. Focus on ROI and working capital.", pain_points=["Inventory costs", "Unpredictable spend"], buying_triggers=["Working capital", "Quarterly targets"], objections=["Cost", "Implementation time"]),
    ]

    return {"house": house, "messages": messages, "personas": personas}


def _pulse_customer_success(now):
    house_id = uuid4()
    house = MessageHouse(
        id=house_id,
        name="Pulse Customer Success",
        source="seed",
        summary="CS platform for SaaS companies. Proactive health scores, automated engagements, and revenue retention.",
        audience="SaaS companies, 50K+ ARR",
        brand_personality="Proactive, insightful, revenue-focused",
        positioning="Pulse turns customer success from reactive firefighting into proactive revenue protection. AI that identifies churn risk before it materializes.",
        tagline="Retention before it's a problem.",
        differentiation="Predictive churn scoring vs NPS surveys. Automated playbook execution vs manual outreach. Revenue attribution vs activity tracking.",
        status=HouseStatus.ACTIVE,
        last_synced=now,
    )

    messages = [
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=1, content="Churn prediction that actually predicts.", variants={"linkedin": "Know who is leaving.", "email": "Know who's leaving"}, personas=["VP Customer Success"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=2, content="Turn reactive CS into proactive retention.", variants={"linkedin": "Proactive retention.", "email": "Proactive retention"}, personas=["CSM"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=3, content="Revenue retention at scale.", variants={"linkedin": "Retention at scale.", "email": "Retention at scale"}, personas=["CCO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=1, content="AI health scores updated daily. Not quarterly surveys.", variants={"linkedin": "Daily health. Not quarterly.", "email": "Daily health scores"}, personas=["VP Customer Success"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=2, content="Automated playbooks trigger at risk threshold.", variants={"linkedin": "Auto-playbooks at risk.", "email": "Auto-playbooks"}, personas=["CSM"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=3, content="Revenue attribution tied to every engagement.", variants={"linkedin": "Every engagement tracked.", "email": "Revenue attribution"}, personas=["CCO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=1, content="Identify 84% of churn risk 30 days early.", variants={"linkedin": "84% churn prediction.", "email": "84% accuracy"}, personas=["VP Customer Success"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=2, content="Reduce churn by 23% on average.", variants={"linkedin": "23% less churn.", "email": "23% churn reduction"}, personas=["CCO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=3, content="Scale CS from 1:100 to 1:200 without headcount.", variants={"linkedin": "2x ratio. No hiring.", "email": "2x efficiency"}, personas=["VP Customer Success"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=4, content="Slack integration triggers outreach automatically.", variants={"linkedin": "Slack triggers CS.", "email": "Slack automation"}, personas=["CSM"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=1, content="312 SaaS companies use Pulse.", variants={"linkedin": "312 SaaS retention.", "email": "312 companies"}, personas=["VP Customer Success"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=2, content="$340M ARR saved from churn across customers.", variants={"linkedin": "$340M saved.", "email": "$340M saved"}, personas=["CCO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=3, content="4.7/5 G2 from 203 CS leaders.", variants={"linkedin": "CS leaders trust.", "email": "4.7/5"}, personas=["CSM"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=1, content="We already do health scores in Excel.", variants={"linkedin": "Excel is manual. Pulse is automatic.", "email": "Excel vs AI"}, personas=["CSM"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=2, content="Our CS team is too small.", variants={"linkedin": "Small team, big impact.", "email": "Small team power"}, personas=["VP Customer Success"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=3, content="CS tools are just activity trackers.", variants={"linkedin": "We track revenue.", "email": "Revenue tracking"}, personas=["CCO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=1, content="Used by 8 SaaS unicorns.", variants={"linkedin": "Unicorn retention.", "email": "8 unicorns"}, personas=["VP Customer Success"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=2, content="\"We caught a churn 6 weeks early.\" — VP CS, $50M ARR SaaS", variants={"linkedin": "6 weeks early.", "email": "\"6 weeks early\""}, personas=["CSM"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=3, content="G2 Leader in CS Platforms Q1 2026.", variants={"linkedin": "G2 CS Leader.", "email": "G2 Leader"}, personas=["CCO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.POSITIONING, priority=1, content="AI-powered CS that protects your revenue.", variants={"linkedin": "Revenue protection.", "email": "Revenue protection"}, personas=["VP Customer Success"], channels=[Channel.ALL]),
    ]

    personas = [
        Persona(id=uuid4(), message_house_id=house_id, name="VP Customer Success", description="VP of CS. Owns retention strategy.", pain_points=["Churn", "Manual outreach", "Scaling"], buying_triggers=["ARR growth", "Churn reduction"], objections=["Manual processes", "Tool consolidation"]),
        Persona(id=uuid4(), message_house_id=house_id, name="CSM", description="Customer Success Manager. Owns portfolio.", pain_points=["Too many accounts", "Reactive vs proactive", "Reporting"], buying_triggers=["Efficiency", "Visibility"], objections=["Integration", "Learning curve"]),
        Persona(id=uuid4(), message_house_id=house_id, name="CCO", description="Chief Customer Officer. Owns revenue retention.", pain_points=["Attribution", "Churn correlation"], buying_triggers=["Revenue goals", "Board"], objections=["Tool justification", "Value proof"]),
    ]

    return {"house": house, "messages": messages, "personas": personas}


def _solara_energy_management(now):
    house_id = uuid4()
    house = MessageHouse(
        id=house_id,
        name="Solara Energy Management",
        source="seed",
        summary="IoT energy management for commercial real estate. Anomaly detection, automated efficiency, and ESG reporting.",
        audience="Commercial property managers, 500K+ sq ft portfolio",
        brand_personality="Efficient, sustainable, data-driven",
        positioning="Solara turns buildings into efficiency engines. IoT-powered insights that cut energy costs 25% and simplify ESG reporting.",
        tagline="Buildings that think. Money that stays.",
        differentiation="IoT-native vs add-on sensors. Real-time automation vs manual overrides. Automated ESG vs spreadsheet reporting.",
        status=HouseStatus.ACTIVE,
        last_synced=now,
    )

    messages = [
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=1, content="Cut energy costs 25% without touching a thermostat.", variants={"linkedin": "25% cost cut.", "email": "25% savings"}, personas=["Facilities Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=2, content="ESG reporting that doesn't require a sustainability team.", variants={"linkedin": "ESG done automatically.", "email": "Auto ESG reporting"}, personas=["CFO", "Sustainability Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=3, content="Turn buildings into competitive advantage.", variants={"linkedin": "Building advantage.", "email": "Building edge"}, personas=["Facilities Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=1, content="Real-time anomaly detection across 10,000+ IoT points.", variants={"linkedin": "IoT at scale.", "email": "10K+ IoT points"}, personas=["Sustainability Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=2, content="Automated HVAC optimization based on occupancy.", variants={"linkedin": "Occupancy-based HVAC.", "email": "Smart HVAC"}, personas=["Facilities Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=3, content="One dashboard across your entire portfolio.", variants={"linkedin": "One dashboard.", "email": "Portfolio dashboard"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=1, content="25% average energy reduction.", variants={"linkedin": "25% less energy.", "email": "25% reduction"}, personas=["Facilities Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=2, content="Cut HVAC maintenance costs by 30%.", variants={"linkedin": "30% less maintenance.", "email": "30% maintenance cut"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=3, content="Automated utility incentive capture.", variants={"linkedin": "Incentives captured.", "email": "Incentive capture"}, personas=["Sustainability Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=4, content="Lease a building advantage with tenants.", variants={"linkedin": "Tenant attraction.", "email": "Tenant value"}, personas=["Facilities Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=1, content="4.2M sq ft under management.", variants={"linkedin": "4.2M sq ft.", "email": "4.2M sq ft"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=2, content="$18M annual energy savings across portfolio.", variants={"linkedin": "$18M saved.", "email": "$18M savings"}, personas=["Facilities Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=3, content="ENERGY STAR Partner of the Year 2025.", variants={"linkedin": "ENERGY STAR Partner.", "email": "ENERGY STAR Partner"}, personas=["Sustainability Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=1, content="We already have BAS.", variants={"linkedin": "We enhance your BAS.", "email": "BAS enhancement"}, personas=["Facilities Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=2, content="Implementation is too invasive.", variants={"linkedin": "Non-invasive install.", "email": "Non-invasive"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=3, content="ROI is too far out.", variants={"linkedin": "18-month ROI.", "email": "18-month ROI"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=1, content="47 CRE portfolios.", variants={"linkedin": "47 portfolios.", "email": "47 portfolios"}, personas=["Facilities Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=2, content="\"Solara cut our energy 28%.\" — Portfolio Dir, OfficeFund", variants={"linkedin": "28% cut.", "email": "\"28% cut\""}, personas=["Sustainability Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=3, content="Greentech ESG Innovation Award 2025.", variants={"linkedin": "Award winner.", "email": "Award winner"}, personas=["CFO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.POSITIONING, priority=1, content="IoT energy management for modern portfolios.", variants={"linkedin": "IoT efficiency.", "email": "IoT energy"}, personas=["Facilities Director"], channels=[Channel.ALL]),
    ]

    personas = [
        Persona(id=uuid4(), message_house_id=house_id, name="Facilities Director", description="Owns building operations and efficiency.", pain_points=["Energy costs", "Maintenance", "Tenant comfort"], buying_triggers=["Cost goals", "Sustainability mandates"], objections=["BAS integration", "Invasive"]),
        Persona(id=uuid4(), message_house_id=house_id, name="CFO", description="Finance lead. Focuses on ROI.", pain_points=["Energy opex", "CapEx justification"], buying_triggers=["ROI targets", "Board pressure"], objections=["ROI timeline", "Implementation"]),
        Persona(id=uuid4(), message_house_id=house_id, name="Sustainability Manager", description="Owns ESG reporting and compliance.", pain_points=["Reporting burden", "Data collection"], buying_triggers=["ESG requirements", "Reporting deadlines"], objections=["Data quality", "Budget"]),
    ]

    return {"house": house, "messages": messages, "personas": personas}


def _vantage_sales_intelligence(now):
    house_id = uuid4()
    house = MessageHouse(
        id=house_id,
        name="Vantage Sales Intelligence",
        source="seed",
        summary="AI sales intelligence and signal detection. Find and close accounts before competitors even know they exist.",
        audience="B2B Sales teams, $5M+ ARR",
        brand_personality="Proactive, predictive, powerful",
        positioning="Vantage finds the buying signals your team is missing. AI that detects intent, predicts timing, and surfaces the leads that actually want to buy.",
        tagline="Signals before they're obvious.",
        differentiation="Real-time signal detection vs weekly research reports. 89% accuracy vs guesswork. 15 data sources vs manual LinkedIn scrolling.",
        status=HouseStatus.ACTIVE,
        last_synced=now,
    )

    messages = [
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=1, content="Find leads before they start shopping.", variants={"linkedin": "Find them first.", "email": "Find first"}, personas=["VP Sales"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=2, content="Close deals your competitors didn't know existed.", variants={"linkedin": "Competitor-proof deals.", "email": "Unbeatable deals"}, personas=["AE"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=3, content="Turn signals into pipeline.", variants={"linkedin": "Signal to pipeline.", "email": "Signal to pipe"}, personas=["Revenue Operations Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=1, content="89% accuracy on buying intent signals.", variants={"linkedin": "89% signals.", "email": "89% accuracy"}, personas=["VP Sales"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=2, content="15 data sources, one unified signal feed.", variants={"linkedin": "One signal feed.", "email": "One feed"}, personas=["Revenue Operations Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=3, content="Score accounts by close likelihood.", variants={"linkedin": "Close likelihood scoring.", "email": "Close scoring"}, personas=["AE"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=1, content="3x more qualified meetings booked.", variants={"linkedin": "3x meetings.", "email": "3x meetings"}, personas=["VP Sales"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=2, content="Cut research time by 75%.", variants={"linkedin": "75% less research.", "email": "75% time saved"}, personas=["AE"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=3, content="Win 27% more competitive deals.", variants={"linkedin": "27% more wins.", "email": "27% win rate"}, personas=["VP Sales"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=4, content="Slack alerts for critical signals.", variants={"linkedin": "Slack signals.", "email": "Slack alerts"}, personas=["Revenue Operations Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=1, content="$1.2B pipeline influenced.", variants={"linkedin": "$1.2B influenced.", "email": "$1.2B influenced"}, personas=["VP Sales"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=2, content="483 sales teams use Vantage.", variants={"linkedin": "483 teams.", "email": "483 teams"}, personas=["Revenue Operations Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=3, content="4.6/5 G2 from 312 sales leaders.", variants={"linkedin": "Sales leaders approve.", "email": "4.6/5"}, personas=["AE"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=1, content="We already have LinkedIn Sales Nav.", variants={"linkedin": "We replace manual scrolling.", "email": "Replace Sales Nav"}, personas=["AE"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=2, content="It's just another data enrichment tool.", variants={"linkedin": "Intent beats enrichment.", "email": "Intent vs enrichment"}, personas=["Revenue Operations Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=3, content="Our team won't use it.", variants={"linkedin": "We've seen 80% adoption.", "email": "80% adoption"}, personas=["VP Sales"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=1, content="Used by 9 SaaS unicorns.", variants={"linkedin": "Unicorn sales teams.", "email": "9 unicorns"}, personas=["VP Sales"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=2, content="\"Vantage found 4 deals we would've missed.\" — VP Sales, $100M ARR SaaS", variants={"linkedin": "4 missed deals found.", "email": "\"4 deals found\""}, personas=["AE"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=3, content="G2 Leader in Sales Intelligence Q1 2026.", variants={"linkedin": "G2 Sales Leader.", "email": "G2 Leader"}, personas=["Revenue Operations Manager"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.POSITIONING, priority=1, content="AI sales intelligence that finds willing buyers.", variants={"linkedin": "Find willing buyers.", "email": "Willing buyers"}, personas=["VP Sales"], channels=[Channel.ALL]),
    ]

    personas = [
        Persona(id=uuid4(), message_house_id=house_id, name="VP Sales", description="VP of Sales. Owns revenue targets.", pain_points=["Pipeline", "Competitive losses", "Forecasting"], buying_triggers=["Growth targets", "Retention goals"], objections=["Tool budget", "Adoption"]),
        Persona(id=uuid4(), message_house_id=house_id, name="AE", description="Account Executive. Owns quota and deals.", pain_points=["Research time", "Finding leads", "Competitive deals"], buying_triggers=["Quota", "Territory"], objections=["Data quality", "Usability"]),
        Persona(id=uuid4(), message_house_id=house_id, name="Revenue Operations Manager", description="Owns sales tech and enablement.", pain_points=["Tool sprawl", "Data quality", "Reporting"], buying_triggers=["Efficiency", "Intelligence"], objections=["Integration", "Complexity"]),
    ]

    return {"house": house, "messages": messages, "personas": personas}


def _atlas_knowledge_management(now):
    house_id = uuid4()
    house = MessageHouse(
        id=house_id,
        name="Atlas Knowledge Management",
        source="seed",
        summary="Internal knowledge base for enterprise. Connect knowledge, not just documents. AI that finds answers.",
        audience="Enterprise companies, 1000+ employees",
        brand_personality="Organized, intelligent, connected",
        positioning="Atlas connects what your team knows to who needs to know it. Internal knowledge that actually gets found.",
        tagline="Knowledge that finds people.",
        differentiation="AI-native search vs keyword matching. Knowledge graph vs folder structure. 91% answer rate vs 40% document findability.",
        status=HouseStatus.ACTIVE,
        last_synced=now,
    )

    messages = [
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=1, content="Knowledge that actually gets found.", variants={"linkedin": "Knowledge that works.", "email": "Knowledge found"}, personas=["CKO", "IT Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=2, content="Connect what you know to who needs it.", variants={"linkedin": "Connect knowledge.", "email": "Connect people"}, personas=["HR Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.HEADLINE, priority=3, content="Stop answering the same questions.", variants={"linkedin": "Stop repeating.", "email": "Stop repeating"}, personas=["IT Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=1, content="91% answer rate. Not 40% document findability.", variants={"linkedin": "91% answers.", "email": "91% answer rate"}, personas=["CKO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=2, content="Knowledge graph, not folder structure.", variants={"linkedin": "Graph, not folders.", "email": "Knowledge graph"}, personas=["IT Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SUBHEAD, priority=3, content="Integrates with Slack, Teams, and Notion.", variants={"linkedin": "Work where you work.", "email": "Integrations"}, personas=["HR Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=1, content="Cut support tickets by 34%.", variants={"linkedin": "34% fewer tickets.", "email": "34% ticket reduction"}, personas=["IT Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=2, content="New hire ramp time cut by 45%.", variants={"linkedin": "45% faster ramp.", "email": "45% faster ramp"}, personas=["HR Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=3, content="Expert finding in 2 clicks.", variants={"linkedin": "Find experts.", "email": "Find experts"}, personas=["CKO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.BENEFIT, priority=4, content="Q&A that improves itself.", variants={"linkedin": "Self-improving Q&A.", "email": "Learning Q&A"}, personas=["IT Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=1, content="78 enterprise knowledge bases.", variants={"linkedin": "78 enterprises.", "email": "78 enterprises"}, personas=["CKO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=2, content="2.1M answers served quarterly.", variants={"linkedin": "2.1M answers.", "email": "2.1M answers"}, personas=["IT Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.PROOF_POINT, priority=3, content="4.7/5 G2 from 189 IT leaders.", variants={"linkedin": "IT leaders approve.", "email": "4.7/5"}, personas=["HR Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=1, content="We already have Notion.", variants={"linkedin": "We enhance Notion.", "email": "Notion enhancement"}, personas=["IT Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=2, content="Content is too scattered.", variants={"linkedin": "We connect scattered content.", "email": "Connect scattered"}, personas=["CKO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.OBJECTION, priority=3, content="No one will contribute.", variants={"linkedin": "We gamify contribution.", "email": "Gamified contribution"}, personas=["HR Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=1, content="Used by 4 Fortune 500 knowledge teams.", variants={"linkedin": "Fortune 500 knowledge.", "email": "4 Fortune 500s"}, personas=["CKO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=2, content="\"Cut our 'how do I' questions 40%.\" — IT Dir, Fortune 100", variants={"linkedin": "40% less questions.", "email": "\"40% reduction\""}, personas=["IT Director"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.SOCIAL_PROOF, priority=3, content="KMWorld Innovation Award 2025.", variants={"linkedin": "Award winner.", "email": "KMWorld award"}, personas=["CKO"], channels=[Channel.ALL]),
        KeyMessage(id=uuid4(), message_house_id=house_id, section_type=SectionType.POSITIONING, priority=1, content="Enterprise knowledge that actually gets found.", variants={"linkedin": "Knowledge found.", "email": "Knowledge found"}, personas=["CKO"], channels=[Channel.ALL]),
    ]

    personas = [
        Persona(id=uuid4(), message_house_id=house_id, name="CKO", description="Chief Knowledge Officer. Owns organizational knowledge.", pain_points=["Lost knowledge", "Finding expertise", "KPI measurement"], buying_triggers=["Digital transformation", "Onboarding issues"], objections=["Adoption", "Content quality"]),
        Persona(id=uuid4(), message_house_id=house_id, name="IT Director", description="Evaluates knowledge tools for engineering.", pain_points=["Tool sprawl", "Search quality", "Integration"], buying_triggers=["Self-serve", "Support reduction"], objections=["Security", "Integration"]),
        Persona(id=uuid4(), message_house_id=house_id, name="HR Director", description="Focuses on employee experience and onboarding.", pain_points=["Onboarding", "Policy access", "Training"], buying_triggers=["New hire velocity", "Access"], objections=["Adoption", "Content creation"]),
    ]

    return {"house": house, "messages": messages, "personas": personas}