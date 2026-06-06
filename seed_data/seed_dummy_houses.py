"""Seed script for 10 dummy message houses across diverse B2B product verticals."""

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path so we can import src modules
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.store import Store
from src.models import (
    CanonDomain, CanonEntry, Persona, GroundingType,
    DomainStatus, SectionType, EntryStatus, Channel
)

def get_houses_data():
    return [
        # 1. Harvest AI — Precision Agriculture Platform
        {
            "name": "Harvest AI Precision Agriculture Platform",
            "summary": "Harvest AI is a precision agriculture platform that uses satellite imagery, IoT soil sensors, and machine learning to help commercial farm operators maximize yield, reduce input costs, and make data-driven planting and harvesting decisions.",
            "audience": "Commercial Farm Operators, Agribusiness, Crop Consultants",
            "brand_personality": "Grounded, practical, and data-driven.",
            "positioning": "Turning field data into harvest decisions — Harvest AI gives commercial growers the agronomic intelligence to produce more with less, season after season.",
            "tagline": "Every acre. Every decision. Optimized.",
            "differentiation": "Harvest AI combines satellite multispectral imagery, in-field IoT sensor networks, and ML yield prediction into one agronomist-grade platform — replacing the guesswork that costs growers an average of 18% of potential yield.",
            "personas": [
                {
                    "name": "Farm Owner / Operator",
                    "description": "Owner-operator of 500–5,000 acre commercial grain or specialty crop farm. Makes all input spend and planting decisions. Answers to no one but the weather.",
                    "pain_points": [
                        "Input costs (seed, fertilizer, chemicals) consuming margins with unpredictable ROI",
                        "No reliable way to know which field zones underperform and why"
                    ],
                    "buying_triggers": [
                        "Back-to-back low-yield seasons on specific field sections",
                        "Fertilizer costs spiking with no visibility into whether application rates are justified"
                    ],
                    "objections": [
                        "Too much tech for a farming operation — complexity isn't worth the learning curve",
                        "Skeptical that software can outperform decades of on-farm experience"
                    ],
                    "entry_content": "Farm owners are being squeezed between rising input costs and flat commodity prices — Harvest AI gives them field-level data to stop spending money where it isn't returning yield."
                },
                {
                    "name": "Agronomist / Crop Consultant",
                    "description": "Independent or co-op agronomist managing recommendations across 10–50 farm clients. Credibility depends on delivering measurable yield improvements.",
                    "pain_points": [
                        "Manually scouting fields is time-consuming and provides only snapshot-in-time data",
                        "Difficult to justify variable-rate application recommendations without continuous field data"
                    ],
                    "buying_triggers": [
                        "Client base growing beyond what manual scouting can serve effectively",
                        "Competitor agronomists winning clients with drone and satellite-backed recommendations"
                    ],
                    "objections": [
                        "Data accuracy in areas with patchy satellite coverage or heavy canopy",
                        "Farmers may bypass the consultant and act directly on platform recommendations"
                    ],
                    "entry_content": "Agronomists using Harvest AI shift from reactive field scouting to proactive zone-by-zone monitoring, giving clients prescriptions backed by continuous data rather than single-point observations."
                },
                {
                    "name": "Agribusiness Operations Director",
                    "description": "Director overseeing operations for a multi-farm agribusiness or farming cooperative managing 20,000+ acres across multiple locations.",
                    "pain_points": [
                        "No centralized view of crop health, yield forecasts, or input spend across all farms",
                        "Inconsistent agronomic practices across farm managers producing wildly variable outcomes"
                    ],
                    "buying_triggers": [
                        "Lender requiring crop performance reporting and yield projections for operating line renewal",
                        "Acquisition of new farms creating need to benchmark and normalize practices"
                    ],
                    "objections": [
                        "Integration with existing farm management ERP and accounting systems",
                        "Data sovereignty — reluctance to share proprietary yield and field data with a software vendor"
                    ],
                    "entry_content": "Operations Directors at multi-farm agribusinesses use Harvest AI to create a single agronomic intelligence layer across all properties, standardizing decision-making and enabling portfolio-level yield forecasting."
                }
            ]
        },
        # 2. ChronoMed — Clinical Trial Management System
        {
            "name": "ChronoMed Clinical Trial Management System",
            "summary": "ChronoMed is a modern clinical trial management system (CTMS) built for emerging biotech and contract research organizations. It streamlines protocol management, patient enrollment tracking, site coordination, and regulatory document management from Phase I through commercialization.",
            "audience": "Biotech Sponsors, CROs, Academic Research Sites",
            "brand_personality": "Precise, compliant, and purpose-built for speed.",
            "positioning": "ChronoMed eliminates the operational drag that slows trials — replacing fragmented spreadsheets and legacy CTMS platforms with a purpose-built system that keeps enrollment on track and auditors satisfied.",
            "tagline": "Trials on time. Data audit-ready.",
            "differentiation": "Unlike legacy CTMS platforms built for pharma giants, ChronoMed is designed for 5–200 person biotech teams running 1–10 concurrent trials — with 2-day onboarding, built-in 21 CFR Part 11 compliance, and an enrollment dashboard that actually reflects ground truth.",
            "personas": [
                {
                    "name": "Principal Investigator (PI)",
                    "description": "MD or PhD leading a clinical trial at a research site. Responsible for protocol adherence, patient safety, and site performance. Time is critically scarce.",
                    "pain_points": [
                        "Buried in regulatory paperwork and site correspondence rather than clinical work",
                        "Enrollment behind projections with no clear visibility into which screening failures are systemic"
                    ],
                    "buying_triggers": [
                        "FDA audit finding citing inadequate essential document management",
                        "Sponsor threatening to close site due to slow enrollment"
                    ],
                    "objections": [
                        "Another system that requires hours of training before being useful",
                        "Worry about data integrity during migration from paper or legacy system"
                    ],
                    "entry_content": "PIs using ChronoMed spend less time chasing documents and more time on patient care — the system surfaces protocol deviations and enrollment gaps before they become audit findings."
                },
                {
                    "name": "Clinical Research Coordinator (CRC)",
                    "description": "Day-to-day site coordinator managing patient scheduling, source data collection, adverse event reporting, and sponsor communications for one or multiple concurrent trials.",
                    "pain_points": [
                        "Tracking consent status, visit schedules, and protocol deviations across multiple patients in spreadsheets",
                        "Hours spent manually preparing for sponsor monitoring visits"
                    ],
                    "buying_triggers": [
                        "Protocol deviation triggered by a missed visit that wasn't flagged in time",
                        "Sponsor mandating use of a CTMS as a site qualification requirement"
                    ],
                    "objections": [
                        "Steep learning curve during active enrollment periods with no time for training",
                        "Uncertainty about whether the system handles multi-protocol patients correctly"
                    ],
                    "entry_content": "CRCs are the backbone of every trial site — ChronoMed replaces their patchwork of spreadsheets, calendars, and paper binders with a single workspace that surfaces what needs attention today."
                },
                {
                    "name": "VP of Clinical Operations",
                    "description": "Executive at a biotech sponsor or CRO overseeing all active trials, site networks, CRO relationships, and regulatory timelines. Accountable for on-time, on-budget study completion.",
                    "pain_points": [
                        "No real-time enrollment visibility across sites — weekly reports are always two weeks stale",
                        "CRO performance is a black box until milestones are missed"
                    ],
                    "buying_triggers": [
                        "Trial running 30%+ behind enrollment projections with no early warning system",
                        "Board or investors demanding a credible timeline to IND filing or Phase II readout"
                    ],
                    "objections": [
                        "Concern about vendor stability — will a startup CTMS vendor be around for the full trial duration",
                        "Change management across site networks that already have established processes"
                    ],
                    "entry_content": "VPs of Clinical Operations choose ChronoMed to get real-time portfolio visibility — replacing the weekly enrollment spreadsheet fire drill with a live dashboard that shows every site's status against projections."
                }
            ]
        },
        # 3. TableTurn — Restaurant Operations Platform
        {
            "name": "TableTurn Restaurant Operations Platform",
            "summary": "TableTurn is an all-in-one restaurant operations platform for multi-location restaurant groups and franchises. It unifies front-of-house table management, kitchen display systems, labor scheduling, and food cost analytics into one operator-grade platform.",
            "audience": "Multi-Location Restaurant Groups, Franchise Operators, Restaurant Chains",
            "brand_personality": "Fast, reliable, and built for operators by operators.",
            "positioning": "TableTurn gives restaurant operators the real-time visibility and control that enterprise software promised but never delivered — without the six-figure implementation bill.",
            "tagline": "Run every location like your best one.",
            "differentiation": "TableTurn replaces the typical restaurant tech stack of 5–8 disconnected systems with one platform that connects reservations, the kitchen, labor scheduling, and food cost tracking — giving operators a single number that matters: profit per cover.",
            "personas": [
                {
                    "name": "Restaurant Owner / Franchisee",
                    "description": "Owner of 2–20 restaurant locations, either independent or as a franchise operator. Personally invested and operationally hands-on. Acutely focused on unit economics.",
                    "pain_points": [
                        "Food and labor cost blowouts driven by waste and overstaffing that aren't visible until the monthly P&L",
                        "Inconsistent guest experience across locations due to no standardized systems"
                    ],
                    "buying_triggers": [
                        "Adding a new location and needing a scalable system before opening day",
                        "Current POS vendor raising prices or discontinuing support"
                    ],
                    "objections": [
                        "Already paying for too many systems — another subscription is a hard sell",
                        "Previous software rollout failed due to staff resistance"
                    ],
                    "entry_content": "Restaurant owners who switch to TableTurn stop managing five separate vendor logins and start managing their business — food cost, labor, and covers in one view, by location."
                },
                {
                    "name": "General Manager",
                    "description": "GM responsible for daily operations at one or more restaurant locations. Manages a team of 20–80 people, lives and dies by the nightly revenue number and weekly labor percentage.",
                    "pain_points": [
                        "Constantly re-doing the labor schedule when staff no-shows or call-outs disrupt the floor plan",
                        "No visibility into kitchen ticket times causing table turn delays during peak service"
                    ],
                    "buying_triggers": [
                        "Health department inspection citing temperature log compliance gaps",
                        "Owner demanding weekly food cost reports that currently require manual calculation"
                    ],
                    "objections": [
                        "Training a high-turnover staff on new software is a constant burden",
                        "Fear that tablet-based systems will fail during a dinner rush"
                    ],
                    "entry_content": "GMs running TableTurn walk into every shift knowing exactly where they stand on labor hours, food prep status, and covers booked — instead of piecing it together from three different systems."
                },
                {
                    "name": "VP of Operations / Director of Ops",
                    "description": "Corporate operations lead overseeing 15–150 restaurant locations for a regional chain or franchise system. Responsible for brand standards, operational consistency, and unit economics across the portfolio.",
                    "pain_points": [
                        "Location performance data lives in disconnected systems and requires manual aggregation for any portfolio-level view",
                        "Identifying underperforming locations before they become cash flow problems"
                    ],
                    "buying_triggers": [
                        "Franchise audit revealing significant operational inconsistency across licensees",
                        "New private equity ownership demanding better unit-level reporting and benchmarking"
                    ],
                    "objections": [
                        "Franchisee buy-in — can't mandate a system change without demonstrating clear operator benefit",
                        "Integration with franchisor royalty reporting and supply chain ordering systems"
                    ],
                    "entry_content": "VPs of Operations use TableTurn to see every location on one screen — food cost, labor, and revenue benchmarked against top performers, without waiting for GMs to submit weekly reports."
                }
            ]
        },
        # 4. PickPath — E-Commerce Warehouse Fulfillment Platform
        {
            "name": "PickPath E-Commerce Fulfillment Platform",
            "summary": "PickPath is a warehouse management and fulfillment optimization platform for high-SKU e-commerce brands and 3PL operators. It uses AI-driven slotting, pick routing, and labor management to help fulfillment centers ship faster with fewer errors and lower labor cost per unit.",
            "audience": "E-Commerce Brands, 3PL Operators, DTC Fulfillment Centers",
            "brand_personality": "Fast, accurate, and operationally obsessed.",
            "positioning": "PickPath turns fulfillment centers from order bottlenecks into brand-defining speed advantages — reducing pick errors, cutting cost-per-unit, and scaling throughput without proportional headcount growth.",
            "tagline": "Ship faster. Pick smarter. Scale confidently.",
            "differentiation": "PickPath uses real-time velocity data to dynamically reslot the warehouse as your SKU mix changes — so your fastest movers are always closest to pack stations, and your pickers never walk an extra mile chasing yesterday's layout.",
            "personas": [
                {
                    "name": "VP of Operations / Fulfillment",
                    "description": "Executive responsible for the entire fulfillment operation across one or more warehouse facilities. Owns throughput, SLA performance, labor cost, and return rates.",
                    "pain_points": [
                        "Labor cost per unit is rising faster than revenue, especially during peak seasons",
                        "Order accuracy errors generating return costs and damaging brand reputation"
                    ],
                    "buying_triggers": [
                        "Peak season (Q4 or Prime Day equivalent) exposing capacity and accuracy limits",
                        "New retail partnership requiring EDI compliance and 99.5%+ order accuracy SLAs"
                    ],
                    "objections": [
                        "WMS migrations are high-risk — downtime during a changeover can be catastrophic",
                        "ROI timeline versus the capital cost of implementation"
                    ],
                    "entry_content": "VPs of Fulfillment Operations choose PickPath when their current WMS can no longer keep pace with SKU growth and order volume — they need a system that optimizes itself as the business changes, not one that requires a consultant every time."
                },
                {
                    "name": "Warehouse Manager",
                    "description": "Day-to-day operations lead managing a team of 20–200 pickers, packers, and receivers across one fulfillment center. Responsible for daily throughput, labor scheduling, and floor safety.",
                    "pain_points": [
                        "New hires take too long to reach productivity because the warehouse layout is non-intuitive",
                        "Manually building pick routes and zone assignments is a daily time drain that produces inconsistent results"
                    ],
                    "buying_triggers": [
                        "Picker errors spiking after a catalog expansion added 500+ new SKUs",
                        "3PL client threatening to move volume after a run of missed SLA days"
                    ],
                    "objections": [
                        "Staff resistance to handheld scanner and directed picking systems",
                        "Downtime risk during the system cutover to a new WMS"
                    ],
                    "entry_content": "Warehouse managers running PickPath see new hire ramp time drop by half — directed picking means workers follow the system instead of memorizing a warehouse layout that changes every week."
                },
                {
                    "name": "E-Commerce Director / DTC Brand Lead",
                    "description": "Brand-side leader responsible for the customer experience end-to-end, including post-purchase shipping speed and return experience. Owns the 3PL relationship and fulfillment SLA.",
                    "pain_points": [
                        "Shipping speed and accuracy directly impact conversion, yet fulfillment is a black box until customers complain",
                        "3PL billing is opaque and costs per order climb unpredictably during peak"
                    ],
                    "buying_triggers": [
                        "Negative reviews citing late or wrong orders starting to appear at scale",
                        "Evaluating a move to self-operated fulfillment to regain cost control and brand control"
                    ],
                    "objections": [
                        "Fear of operational complexity that comes with in-house fulfillment",
                        "Uncertainty about whether platform can handle new product categories or bundling complexity"
                    ],
                    "entry_content": "E-commerce brands running on PickPath finally get visibility into what's happening after the order is placed — real-time pick status, SLA risk alerts, and per-SKU accuracy rates tied directly to customer experience metrics."
                }
            ]
        },
        # 5. PawChart — Veterinary Practice Management System
        {
            "name": "PawChart Veterinary Practice Management System",
            "summary": "PawChart is a cloud-native veterinary practice management system built for multi-doctor clinics and veterinary group practices. It unifies electronic medical records, appointment scheduling, pharmacy inventory, client communications, and financial reporting in one platform purpose-built for veterinary workflows.",
            "audience": "Veterinary Clinics, Multi-Location Vet Groups, Emergency Animal Hospitals",
            "brand_personality": "Caring, reliable, and built for the pace of a busy clinic.",
            "positioning": "PawChart is the practice management system that veterinary teams actually enjoy using — reducing administrative burden so doctors spend more time with patients and less time with paperwork.",
            "tagline": "Less admin. More medicine.",
            "differentiation": "PawChart is purpose-built for veterinary-specific workflows — multi-species SOAP templates, controlled substance logging, weight-based dosing calculators, and species-specific vaccine protocols are built in, not bolted on as add-ons.",
            "personas": [
                {
                    "name": "Practice Owner (Veterinarian)",
                    "description": "DVM who owns a 2–10 doctor veterinary practice. Splits time between clinical work and business management. Responsible for profitability, staff retention, and client experience.",
                    "pain_points": [
                        "Missed charges due to treatments not being captured in the record before checkout",
                        "Outdated practice management software slowing down the front desk and frustrating staff"
                    ],
                    "buying_triggers": [
                        "Current software vendor raising renewal pricing significantly or ending support",
                        "Associate DVMs leaving partly due to frustration with antiquated clinic systems"
                    ],
                    "objections": [
                        "Data migration from the current system without losing years of patient history",
                        "Downtime during cutover — can't go dark in a clinical setting"
                    ],
                    "entry_content": "Practice owners switching to PawChart see an immediate reduction in missed charges and a measurable improvement in staff morale — the system captures charges at the point of care instead of relying on doctors to remember to add them at checkout."
                },
                {
                    "name": "Clinic Manager",
                    "description": "Non-DVM practice administrator managing scheduling, client communications, inventory, billing, and staff coordination for a busy clinic. The operational hub of the practice.",
                    "pain_points": [
                        "Pharmacy and vaccine inventory tracked in a separate spreadsheet that is always out of date",
                        "Client appointment reminders and follow-up communications are manual and inconsistent"
                    ],
                    "buying_triggers": [
                        "Controlled substance discrepancy triggering a DEA compliance review",
                        "Appointment no-show rate climbing because reminder system is unreliable"
                    ],
                    "objections": [
                        "Training a mixed-experience front desk team on a new system during busy clinic hours",
                        "Whether automated reminders can handle the complexity of different species recall schedules"
                    ],
                    "entry_content": "Clinic managers using PawChart eliminate the parallel spreadsheet life — inventory, reminders, and recall scheduling are all in the same system as the medical record, so data is accurate without double entry."
                },
                {
                    "name": "Veterinary Group COO",
                    "description": "Operations leader overseeing 5–40 veterinary clinic locations under a private equity-backed group or corporate veterinary company. Responsible for operational standardization, EBITDA improvement, and integration of acquired practices.",
                    "pain_points": [
                        "Acquired clinics running on 6 different PIMS systems, making portfolio-level financial reporting nearly impossible",
                        "No benchmarking visibility to identify which clinics are underperforming on revenue per doctor or capture rate"
                    ],
                    "buying_triggers": [
                        "PE board requiring consolidated financial and clinical metrics across all locations",
                        "New acquisition pipeline requiring a standard PIMS for integration playbook"
                    ],
                    "objections": [
                        "Clinical staff resistance to platform standardization — doctors have strong preferences for familiar systems",
                        "Multi-location rollout timeline vs ongoing acquisition pace"
                    ],
                    "entry_content": "Veterinary group COOs choose PawChart as their consolidation platform because the migration tooling actually works — they can onboard an acquired clinic in two weeks and immediately have it contributing to the portfolio dashboard."
                }
            ]
        },
        # 6. BuildIQ — Construction Project Intelligence Platform
        {
            "name": "BuildIQ Construction Project Intelligence Platform",
            "summary": "BuildIQ is a construction project intelligence platform for general contractors and real estate developers. It connects project schedules, subcontractor performance, RFI and submittal tracking, daily field reports, and cost forecasting in one collaborative environment accessible from the field.",
            "audience": "General Contractors, Real Estate Developers, Construction Project Owners",
            "brand_personality": "Rugged, practical, and relentlessly focused on schedule and budget.",
            "positioning": "BuildIQ gives GCs and owners the real-time project intelligence to see problems 30 days before they become schedule overruns — turning reactive project management into proactive control.",
            "tagline": "Build ahead of problems. Not behind them.",
            "differentiation": "BuildIQ surfaces the early warning signals buried in RFI logs, submittal delays, and daily reports — using pattern recognition to flag which current issues are statistically correlated with schedule slippage on similar projects, before the delay lands on the critical path.",
            "personas": [
                {
                    "name": "General Contractor / Project Executive",
                    "description": "Senior GC leader responsible for delivering a portfolio of 3–20 concurrent construction projects. Manages subcontractor relationships, owner expectations, and project P&L.",
                    "pain_points": [
                        "Subcontractor delays cascading across trades without visibility until the schedule is already broken",
                        "Change order disputes with owners requiring weeks of document forensics to resolve"
                    ],
                    "buying_triggers": [
                        "Liquidated damages clause triggered on a major project due to a preventable schedule overrun",
                        "Owner requiring a collaborative project management platform as a contract requirement"
                    ],
                    "objections": [
                        "Field crews and subcontractors won't adopt another app on top of the ones they already ignore",
                        "Cost of implementation during a period when every PM is already overstretched"
                    ],
                    "entry_content": "GCs using BuildIQ stop managing projects in email and start managing them in data — every RFI, submittal, and daily report feeds into a schedule impact model that tells project executives which fires to fight today."
                },
                {
                    "name": "Project Manager (Construction)",
                    "description": "PM responsible for day-to-day management of one or two active construction projects. Coordinates subs, manages document flow, tracks schedule, and is the primary owner interface.",
                    "pain_points": [
                        "RFI and submittal logs maintained in spreadsheets that are perpetually out of sync with reality",
                        "Preparing owner updates requires pulling data from four different systems and still feels incomplete"
                    ],
                    "buying_triggers": [
                        "Owner demanding weekly real-time dashboards instead of PDF progress reports",
                        "Audit finding subcontractor safety violations that weren't visible in the daily report log"
                    ],
                    "objections": [
                        "Resistance to yet another SaaS tool when the team barely uses the last one that was mandated",
                        "Worry about mobile reliability on job sites with poor cellular coverage"
                    ],
                    "entry_content": "Construction PMs on BuildIQ spend less time compiling reports and more time managing the project — the system aggregates field data from subs and foremen automatically, so the weekly owner report takes 20 minutes instead of a full day."
                },
                {
                    "name": "Real Estate Developer / Owner",
                    "description": "Developer or institutional owner overseeing one or more active construction projects. Focused on schedule, budget adherence, and opening on time. Often not a construction expert.",
                    "pain_points": [
                        "Entirely dependent on GC-provided information that may be optimistic or incomplete",
                        "Budget contingency disappearing into change orders that were never properly justified"
                    ],
                    "buying_triggers": [
                        "Project significantly over budget or behind schedule with no early warning from the GC",
                        "Lender requiring independent project monitoring and reporting as a draw condition"
                    ],
                    "objections": [
                        "GC may not want the owner having real-time visibility into field issues",
                        "Not enough internal construction expertise to interpret project data independently"
                    ],
                    "entry_content": "Developers using BuildIQ stop being passive recipients of GC progress reports and start having independent visibility into their project — live schedule status, pending change order value, and cost-to-complete forecasting that doesn't depend on what the GC chooses to share."
                }
            ]
        },
        # 7. LearnLoop — Corporate Learning & Skills Development Platform
        {
            "name": "LearnLoop Corporate Learning and Skills Development Platform",
            "summary": "LearnLoop is an AI-powered corporate learning and skills development platform for mid-enterprise companies. It moves beyond static LMS course catalogs to deliver personalized learning paths, skills gap analysis, internal knowledge sharing, and measurable capability building tied to business outcomes.",
            "audience": "Corporate L&D Teams, HR Leaders, Business Unit Managers",
            "brand_personality": "Curious, practical, and relentlessly focused on measurable learning outcomes.",
            "positioning": "LearnLoop replaces the corporate LMS graveyard of mandatory compliance modules with a learning experience that employees actually use — personalized to their role, their skills gaps, and where they want to go next.",
            "tagline": "Skills that move the business. Learning that sticks.",
            "differentiation": "LearnLoop connects learning activity directly to skills inventory and workforce planning — so L&D leaders can show HR and the business not just completion rates, but which capabilities the organization is actually building and where the critical gaps remain.",
            "personas": [
                {
                    "name": "Chief Learning Officer (CLO) / VP of L&D",
                    "description": "Executive owning the corporate learning strategy, L&D budget, and workforce capability agenda. Reports to CHRO and is under increasing pressure to demonstrate business impact beyond training hours and completion rates.",
                    "pain_points": [
                        "L&D is viewed as a cost center — leadership wants proof that learning investment translates to business performance",
                        "Current LMS completion data doesn't tell the organization anything about whether skills are actually being built"
                    ],
                    "buying_triggers": [
                        "CEO or board identifying critical skills gaps as a strategic risk to the company's roadmap",
                        "High-potential employee attrition attributed in exit interviews to lack of development opportunities"
                    ],
                    "objections": [
                        "Content migration from the existing LMS is a massive undertaking the team doesn't have bandwidth for",
                        "Skepticism about employee adoption after previous learning platform rollouts that went unused"
                    ],
                    "entry_content": "CLOs choose LearnLoop when they're ready to move from reporting completion percentages to reporting skills built — the platform connects learning activity to skills inventory so L&D can finally have a business conversation, not just a training conversation."
                },
                {
                    "name": "L&D Program Manager",
                    "description": "Hands-on L&D professional designing, curating, and managing learning programs for specific functions or the whole organization. Responsible for content quality, learner engagement, and reporting.",
                    "pain_points": [
                        "Building and maintaining learning paths in the current LMS requires significant admin time for minimal learner value",
                        "No way to see which content is actually helping people develop versus which is just getting click-throughs for compliance"
                    ],
                    "buying_triggers": [
                        "New functional leader requesting a skills development program for their team with no additional headcount",
                        "Annual engagement survey showing employees feel development opportunities are inadequate"
                    ],
                    "objections": [
                        "AI-generated learning recommendations feel impersonal and may not fit company culture or specific role nuances",
                        "Adding another platform creates more content fragmentation rather than less"
                    ],
                    "entry_content": "L&D Program Managers using LearnLoop spend less time building course catalogs in an authoring tool and more time curating meaningful learning journeys — the platform handles personalization and sequencing while they focus on content strategy."
                },
                {
                    "name": "Business Unit / Functional Leader",
                    "description": "VP or Director of a business function (Sales, Engineering, Operations) who owns headcount and capability development within their team. Sees L&D as a tool for performance, not compliance.",
                    "pain_points": [
                        "New hires take too long to reach productivity because onboarding is generic, not role-specific",
                        "No structured way to develop critical technical or functional skills — it happens informally or not at all"
                    ],
                    "buying_triggers": [
                        "Team missing key skill areas that are blocking a product or market initiative",
                        "High performer leaving because they didn't see a development path inside the company"
                    ],
                    "objections": [
                        "Employees don't have time for structured learning alongside their current workload",
                        "Previous mandatory training programs created resentment that poisons new learning initiatives"
                    ],
                    "entry_content": "Business leaders who use LearnLoop to build team capability see faster time-to-productivity for new hires and higher retention among high performers who see a visible development path — the platform makes growth tangible, not a vague promise."
                }
            ]
        },
        # 8. PropEdge — Real Estate Investment Analytics Platform
        {
            "name": "PropEdge Real Estate Investment Analytics Platform",
            "summary": "PropEdge is an investment analytics platform for real estate private equity funds, REITs, and family office property investors. It aggregates market data, property-level financials, lease abstracts, and comparable transaction data to power acquisition underwriting, portfolio monitoring, and investor reporting.",
            "audience": "Real Estate Private Equity, REITs, Family Office Property Investors",
            "brand_personality": "Analytical, disciplined, and built for investors who move on data.",
            "positioning": "PropEdge compresses the underwriting timeline from weeks to days — giving real estate investment teams the market intelligence and financial modeling tools to underwrite more deals faster without adding analysts.",
            "tagline": "Underwrite faster. Invest with conviction.",
            "differentiation": "PropEdge connects public market data, proprietary comp databases, and your own portfolio financials in one workspace — so underwriting teams aren't rebuilding the same models from scratch on every deal and market research isn't trapped in individual analysts' spreadsheets.",
            "personas": [
                {
                    "name": "Managing Director / Partner (Real Estate PE)",
                    "description": "Investment decision-maker at a real estate PE fund or REIT managing $200M–$5B in assets. Responsible for deal sourcing, investment committee approval, and LP relationships.",
                    "pain_points": [
                        "Deal pipeline moves too slowly — by the time underwriting is complete, competitive deals have closed",
                        "Portfolio-level performance reporting to LPs is time-consuming and relies on data that's always 60+ days old"
                    ],
                    "buying_triggers": [
                        "Losing three deals in a row to faster-moving competitors who can close underwriting in 48 hours",
                        "LP demanding enhanced quarterly reporting with market context, not just property financials"
                    ],
                    "objections": [
                        "Proprietary investment models are a competitive advantage — concern about data security and model integrity",
                        "Analysts are already comfortable with Excel; adoption of a new platform slows the team down initially"
                    ],
                    "entry_content": "Managing Directors at real estate PE funds use PropEdge to compress the underwriting cycle — getting to investment committee in days instead of weeks means they can run a disciplined process without losing competitive deals to faster-moving shops."
                },
                {
                    "name": "Real Estate Analyst / Associate",
                    "description": "Junior to mid-level investment professional doing the heavy lifting on underwriting — financial modeling, market research, lease abstraction, and comp analysis. Drowning in Excel and disconnected data sources.",
                    "pain_points": [
                        "Spending 70% of underwriting time on data gathering and model setup rather than actual investment analysis",
                        "Comp data lives in email threads, broker pitchbooks, and CoStar exports that can't be easily cross-referenced"
                    ],
                    "buying_triggers": [
                        "New analyst joins the team and there's no systematic way to get them productive on underwriting",
                        "Investment committee asking for sensitivity analyses that take two days to run in the current Excel model"
                    ],
                    "objections": [
                        "Platform may not handle the specific asset class nuances (industrial vs. multifamily vs. office) with the required depth",
                        "Exporting to Excel for final presentation means maintaining two versions of the model"
                    ],
                    "entry_content": "Real estate analysts using PropEdge spend their time analyzing deals, not building the same market research package from scratch on every acquisition — the platform automates data aggregation so the analyst can focus on the judgment calls that actually require expertise."
                },
                {
                    "name": "Asset Manager",
                    "description": "Professional responsible for the ongoing performance of a portfolio of acquired properties — managing leasing, capital improvements, NOI growth, and eventual disposition. The bridge between acquisition underwriting and realized returns.",
                    "pain_points": [
                        "Property-level performance data is scattered across multiple systems and requires manual aggregation for any portfolio view",
                        "Business plan variances aren't identified until quarterly reporting, by which point corrective action is expensive"
                    ],
                    "buying_triggers": [
                        "Asset significantly underperforming underwriting projections with no early warning system in place",
                        "Fund raising new capital that requires demonstrating systematic portfolio monitoring capability to LPs"
                    ],
                    "objections": [
                        "Property management data integration — different PM software across the portfolio creates data standardization headaches",
                        "Platform switching cost when existing workflows are deeply embedded in current tools"
                    ],
                    "entry_content": "Asset managers using PropEdge catch business plan variances early — live NOI tracking against underwriting projections means they can act on lease-up pace or expense trends before a quarterly review surfaces a problem that's already compounded."
                }
            ]
        },
        # 9. FleetNow — Fleet Management and Route Optimization Platform
        {
            "name": "FleetNow Fleet Management and Route Optimization Platform",
            "summary": "FleetNow is a fleet management and intelligent route optimization platform for transportation companies, regional distributors, and service fleet operators. It combines real-time GPS tracking, AI-powered route optimization, driver behavior monitoring, fuel analytics, and maintenance forecasting in one operations platform.",
            "audience": "Regional Trucking, Last-Mile Delivery, Field Service Fleets",
            "brand_personality": "Reliable, efficient, and built for the people who keep the wheels moving.",
            "positioning": "FleetNow helps fleet operators do more with the trucks and drivers they already have — reducing fuel spend, extending vehicle life, and cutting idle time without hiring a dedicated fleet analyst.",
            "tagline": "Every mile optimized. Every truck protected.",
            "differentiation": "FleetNow's route optimization doesn't just calculate the shortest path — it factors real-time traffic, driver hours-of-service compliance, vehicle load capacity, customer time windows, and fuel efficiency simultaneously, finding routes that are actually executable, not just theoretically optimal.",
            "personas": [
                {
                    "name": "Fleet Director / VP of Transportation",
                    "description": "Executive owning the P&L of a fleet operation with 50–500 vehicles. Responsible for cost-per-mile, on-time delivery performance, DOT compliance, and driver retention.",
                    "pain_points": [
                        "Fuel and maintenance costs climbing faster than freight rates, compressing margins on every load",
                        "DOT compliance exposure due to manual HOS tracking that relies on driver self-reporting"
                    ],
                    "buying_triggers": [
                        "DOT audit finding violations that could put the operating authority at risk",
                        "Insurance renewal with a premium increase tied to accident frequency and driver behavior data"
                    ],
                    "objections": [
                        "Drivers' union may push back on electronic monitoring perceived as surveillance",
                        "Previous telematics rollout produced data nobody used because reporting was too complex"
                    ],
                    "entry_content": "Fleet Directors who deploy FleetNow see fuel cost reduction in the first 60 days — the combination of route optimization and idle time reduction delivers measurable savings before the annual maintenance benefits compound."
                },
                {
                    "name": "Dispatcher / Fleet Operations Manager",
                    "description": "Day-to-day operations lead managing driver assignments, route planning, delivery confirmation, and real-time problem-solving when the inevitable delays and breakdowns occur.",
                    "pain_points": [
                        "Manually building routes each morning for 20–100 drivers takes hours and produces suboptimal results",
                        "Customer calls asking for ETA updates when dispatcher has no real-time visibility into where trucks actually are"
                    ],
                    "buying_triggers": [
                        "Customer SLA penalty charged because delayed delivery wasn't visible until after the window closed",
                        "Key dispatcher leaving and taking all the institutional route knowledge with them"
                    ],
                    "objections": [
                        "Concern that automated routing doesn't account for driver knowledge of local roads and customer preferences",
                        "Reliability of mobile app for drivers in rural or low-coverage areas"
                    ],
                    "entry_content": "Dispatchers running FleetNow get their mornings back — AI-generated routes load overnight based on the day's orders, leaving dispatchers time to handle exceptions rather than build from scratch before the first truck rolls."
                },
                {
                    "name": "Driver / Field Operator",
                    "description": "Commercial driver operating a delivery or service vehicle under a demanding schedule. Primary user of the mobile interface. Skeptical of technology that adds steps to their day rather than removing them.",
                    "pain_points": [
                        "Routes loaded into the GPS don't account for real-world constraints the driver already knows about",
                        "Paperwork for pre-trip inspections, delivery confirmations, and incident reports eats into drive time and unpaid hours"
                    ],
                    "buying_triggers": [
                        "Company mandating electronic logging device (ELD) upgrade to replace paper logs",
                        "New mobile app that eliminates paper forms is positioned as a driver-benefit change"
                    ],
                    "objections": [
                        "Fear that tracking is primarily being used for discipline rather than to help drivers",
                        "Frustration if the app is slow, requires multiple logins, or doesn't work offline"
                    ],
                    "entry_content": "Drivers using the FleetNow mobile app spend less time on paperwork and get route updates that actually reflect current conditions — the system is fast enough that it helps rather than slows them down, which is the only way driver adoption happens at scale."
                }
            ]
        },
        # 10. TeleCare — Virtual Care and Telemedicine Platform
        {
            "name": "TeleCare Virtual Care and Telemedicine Platform",
            "summary": "TeleCare is a virtual care platform for health systems, physician groups, and digital health companies. It provides video visit infrastructure, async clinical messaging, remote patient monitoring integration, care coordination workflows, and billing automation — giving providers the tools to deliver high-quality care outside the clinic walls.",
            "audience": "Health Systems, Physician Groups, Digital Health Companies",
            "brand_personality": "Compassionate, clinically rigorous, and reliable under pressure.",
            "positioning": "TeleCare gives health systems the infrastructure to extend care beyond the clinic without building it themselves — reducing no-show rates, expanding access, and enabling the chronic disease management programs that improve outcomes and generate recurring revenue.",
            "tagline": "Care without boundaries. Revenue without gaps.",
            "differentiation": "TeleCare handles the full telehealth revenue cycle — from eligibility verification and consent collection before the visit to payer-specific billing rule application and claim submission after — so provider organizations don't need a separate billing workflow for virtual care.",
            "personas": [
                {
                    "name": "Chief Medical Officer (CMO) / Medical Director",
                    "description": "Physician leader responsible for clinical program design, quality outcomes, and provider satisfaction at a health system or large physician group. Gatekeeper for any technology that touches the clinical workflow.",
                    "pain_points": [
                        "Telehealth platforms that look consumer-friendly but frustrate clinicians with poor EHR integration and disruptive workflow changes",
                        "No way to measure whether virtual care is delivering equivalent outcomes to in-person visits across chronic disease programs"
                    ],
                    "buying_triggers": [
                        "CMS reimbursement policy change making remote patient monitoring newly billable at scale",
                        "Patient satisfaction scores declining in access and convenience categories that telehealth directly addresses"
                    ],
                    "objections": [
                        "Clinical liability if technology failure results in a missed diagnosis or delayed care",
                        "Physician burnout risk if virtual care adds documentation burden on top of existing in-person workload"
                    ],
                    "entry_content": "CMOs who deploy TeleCare see provider adoption because the platform works inside the existing EHR workflow rather than parallel to it — clinicians document in one place, and the virtual visit is just another encounter type, not a second system to manage."
                },
                {
                    "name": "Telehealth Program Manager",
                    "description": "Clinical operations professional standing up and managing a virtual care program within a health system or physician group. Owns the operational workflows, provider training, patient onboarding, and program metrics.",
                    "pain_points": [
                        "Virtual care no-show rates significantly higher than in-person visits, undermining program economics",
                        "Manual scheduling and patient outreach processes making it impossible to scale the program beyond a pilot"
                    ],
                    "buying_triggers": [
                        "Health system leadership demanding the telehealth pilot scale to 10x volume within 12 months",
                        "Payer contracting opportunity that requires demonstrating a credentialed telehealth delivery capability"
                    ],
                    "objections": [
                        "Patient digital literacy barriers — older or underserved patient populations may not be able to use video visits effectively",
                        "Integration complexity with the existing scheduling and EHR system the organization has already invested in"
                    ],
                    "entry_content": "Telehealth Program Managers running TeleCare cut no-show rates with automated pre-visit reminders and one-click patient join links — they stop spending half their time on scheduling logistics and start managing a program that actually scales."
                },
                {
                    "name": "Patient Care Coordinator / Nurse Navigator",
                    "description": "Clinical support professional managing patient outreach, appointment scheduling, care plan follow-up, and chronic disease monitoring for a panel of patients. The human infrastructure of any telehealth program.",
                    "pain_points": [
                        "Following up with patients between visits relies on phone calls that go unanswered and unreturned",
                        "Remote monitoring device data arrives in a separate portal the coordinator has to check independently from the EHR"
                    ],
                    "buying_triggers": [
                        "Panel size expanding beyond what current manual outreach workflows can support",
                        "Care quality measure performance declining because between-visit touchpoints aren't happening consistently"
                    ],
                    "objections": [
                        "Patient privacy concerns about video visit technology and where recordings or data are stored",
                        "Technical support burden falls on the coordinator when patients can't connect to a video visit"
                    ],
                    "entry_content": "Care coordinators using TeleCare manage larger patient panels without burning out — async messaging means patients can respond when it's convenient for them, and remote monitoring alerts surface in the same workspace as the care plan rather than a separate app."
                }
            ]
        }
    ]

def seed_databases():
    # Loop over both possible databases to ensure the container volume AND local dev has them
    db_paths = ["msgstack.db", "data/msgstack.db"]
    houses_data = get_houses_data()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for db_path in db_paths:
        print(f"--- Seeding database at {db_path} ---")
        try:
            store = Store(db_path)
            store.init()
        except Exception as e:
            print(f"Failed to initialize Store for {db_path}: {e}")
            continue

        for i, house_def in enumerate(houses_data, 1):
            house_name = house_def["name"]

            # Clean up existing house if it has the same name
            try:
                existing = store.get_house_by_name(house_name)
                if existing:
                    print(f"Removing existing messaging house '{house_name}' (ID: {existing.id})")
                    store.delete_canon_domain(existing.id)
            except Exception as e:
                print(f"Error checking/deleting existing house '{house_name}': {e}")

            house_id = uuid.uuid4()
            domain = CanonDomain(
                id=house_id,
                name=house_name,
                source="google_drive",
                source_id=f"dummy_{i:03d}_{uuid.uuid4().hex[:8]}",
                grounding_type=GroundingType.PERSONA_LIBRARY,
                summary=house_def["summary"],
                audience=house_def["audience"],
                brand_personality=house_def["brand_personality"],
                positioning=house_def["positioning"],
                tagline=house_def["tagline"],
                differentiation=house_def["differentiation"],
                status=DomainStatus.ACTIVE,
                last_synced=now
            )

            try:
                # Upsert CanonDomain
                store.upsert_canon_domain(domain)
                print(f"[{i}/10] Created CanonDomain: {house_name} (ID: {house_id})")

                # Upsert Personas and CanonEntries
                for priority, p_def in enumerate(house_def["personas"], 1):
                    persona_id = uuid.uuid4()
                    persona = Persona(
                        id=persona_id,
                        canon_domain_id=house_id,
                        name=p_def["name"],
                        description=p_def["description"],
                        pain_points=p_def["pain_points"],
                        buying_triggers=p_def["buying_triggers"],
                        objections=p_def["objections"],
                        status=EntryStatus.APPROVED
                    )
                    store.upsert_persona(persona)

                    entry_id = uuid.uuid4()
                    entry = CanonEntry(
                        id=entry_id,
                        canon_domain_id=house_id,
                        section_type=SectionType.PERSONA_DETAIL,
                        priority=priority,
                        content=p_def["entry_content"],
                        personas=[p_def["name"]],
                        channels=[Channel.ALL],
                        status=EntryStatus.APPROVED
                    )
                    store.upsert_canon_entry(entry)

                print(f"     Successfully seeded 3 personas and 3 canon entries for '{house_name}'")
            except Exception as e:
                print(f"Failed to seed '{house_name}': {e}")

        print(f"Finished seeding {db_path}\n")

if __name__ == "__main__":
    seed_databases()
