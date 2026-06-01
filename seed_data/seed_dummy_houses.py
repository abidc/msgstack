"""Seed script for 10 dummy message houses modeled after the ServiceNow persona library."""

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
        # 1. IT Service Management (ITSM)
        {
            "name": "IT Service Management Messaging House",
            "summary": "This document covers buyer and user personas related to IT Service Management, focusing on the roles involved in IT support and service processes and their specific needs.",
            "audience": "IT, Operations, Helpdesk",
            "brand_personality": "Empathetic, reliable, and innovative.",
            "positioning": "Transforming IT operations through automation and AI-driven service desk solutions.",
            "tagline": "Resolve IT tickets instantly and free time for strategic technology initiatives.",
            "differentiation": "ServiceNow's AI Agents autonomously resolve IT support requests, reducing ticket queues and resolving employee issues in seconds.",
            "personas": [
                {
                    "name": "CIO",
                    "description": "Chief Information Officer responsible for overall IT strategy, budget, and business alignment.",
                    "pain_points": [
                        "Budget constraints limiting digital transformation",
                        "SLA breaches impacting business productivity"
                    ],
                    "buying_triggers": [
                        "Need to lower cost-per-ticket",
                        "Frequent escalations of service outages"
                    ],
                    "objections": [
                        "High integration costs with existing legacy infrastructure",
                        "Unproven AI resolution reliability"
                    ],
                    "entry_content": "CIOs are frustrated by mounting IT support costs and SLA breaches that drag down business-wide productivity."
                },
                {
                    "name": "IT Manager",
                    "description": "Operations lead managing helpdesk teams and ticket resolution.",
                    "pain_points": [
                        "High ticket volumes causing technician burnout",
                        "Inefficient manual categorization and routing of issues"
                    ],
                    "buying_triggers": [
                        "Backlog of unaddressed low-tier tickets",
                        "Team fatigue from repetitive resets and setups"
                    ],
                    "objections": [
                        "Learning curve for service agents to adopt new software",
                        "Risk of automated systems misrouting critical incidents"
                    ],
                    "entry_content": "IT Managers struggle with overwhelming ticket backlogs and manual routing that burns out support teams."
                },
                {
                    "name": "Service Desk Agent",
                    "description": "Front-line support representative handling user tickets.",
                    "pain_points": [
                        "Dealing with frustrated users over delayed responses",
                        "Time wasted on routine password resets and simple access requests"
                    ],
                    "buying_triggers": [
                        "Desire for single-pane-of-glass workspace",
                        "Need for automated knowledge article suggestions"
                    ],
                    "objections": [
                        "Fear that AI agents will replace their jobs",
                        "Clunky user interface in new tools"
                    ],
                    "entry_content": "Service Desk Agents spend too much time on repetitive, low-value issues rather than solving complex technical problems."
                }
            ]
        },
        # 2. Customer Service Delivery
        {
            "name": "Customer Service Delivery Messaging House",
            "summary": "This document covers buyer and user personas related to Customer Service Delivery, focusing on the roles involved in customer support processes and their specific needs.",
            "audience": "Customer Support, Customer Success, Operations",
            "brand_personality": "Empathetic, responsive, and strategic.",
            "positioning": "Transforming customer support through automation and AI-driven case resolution.",
            "tagline": "Solve customer issues in real-time and boost lifetime value.",
            "differentiation": "ServiceNow's AI Agents autonomously resolve customer inquiries and orchestrate multi-department resolutions instantly.",
            "personas": [
                {
                    "name": "VP of Customer Success",
                    "description": "Executive champion of customer retention, CSAT, and Net Promoter Score (NPS).",
                    "pain_points": [
                        "Sinking CSAT scores due to slow response times",
                        "High agent turnover driving up training costs"
                    ],
                    "buying_triggers": [
                        "Board pressure to scale support without headcount linear growth",
                        "Spiking customer churn rates"
                    ],
                    "objections": [
                        "AI communication appearing cold or robotic to customers",
                        "Loss of human touch in delicate escalation scenarios"
                    ],
                    "entry_content": "VPs of Customer Success are frustrated by lagging CSAT scores and high support costs that limit scaling."
                },
                {
                    "name": "Customer Support Manager",
                    "description": "Operations lead managing frontline support teams and queues.",
                    "pain_points": [
                        "Inefficient handoffs between support tiers and product teams",
                        "Lack of real-time visibility into customer sentiment and queue bottlenecks"
                    ],
                    "buying_triggers": [
                        "Agent burnouts due to repetitive tier-1 cases",
                        "Customer complaints about repeating their issues to different agents"
                    ],
                    "objections": [
                        "Implementation disruption to live chat queues",
                        "Complex configuration of automated workflows"
                    ],
                    "entry_content": "Customer Support Managers struggle with siloed customer data and tool-switching that delays case resolution."
                },
                {
                    "name": "Support Agent",
                    "description": "Frontline representative answering customer queries.",
                    "pain_points": [
                        "Juggling multiple disparate tools to find customer history",
                        "High stress from handling angry customers waiting in long queues"
                    ],
                    "buying_triggers": [
                        "Need for instant context on customer accounts",
                        "Desire to automate repetitive copy-paste responses"
                    ],
                    "objections": [
                        "Fear of automated macros making mistakes",
                        "System downtime during shift handovers"
                    ],
                    "entry_content": "Support Agents are overwhelmed by handling repetitive tier-1 cases rather than delivering personalized care."
                }
            ]
        },
        # 3. Security Operations (SecOps)
        {
            "name": "Security Operations Messaging House",
            "summary": "This document covers buyer and user personas related to Security Operations, focusing on the roles involved in security incident response and vulnerability management.",
            "audience": "Security, IT, Compliance",
            "brand_personality": "Vigilant, precise, and authoritative.",
            "positioning": "Accelerating threat response through AI-powered automation and security orchestration.",
            "tagline": "Detect threats faster, respond smarter, and secure the enterprise.",
            "differentiation": "ServiceNow's AI Agents autonomously triage and remediate security alerts, reducing exposure window from days to minutes.",
            "personas": [
                {
                    "name": "CISO",
                    "description": "Chief Information Security Officer leading cyber risk strategy and compliance.",
                    "pain_points": [
                        "High risk of existential data breaches",
                        "Regulatory compliance complexity and audit failures"
                    ],
                    "buying_triggers": [
                        "New compliance directives (e.g., DORA, SEC mandates)",
                        "Recent security near-miss in the sector"
                    ],
                    "objections": [
                        "System integrations exposing additional attack surfaces",
                        "Lack of trust in AI taking automated containment actions"
                    ],
                    "entry_content": "CISOs face extreme pressure to secure the enterprise and meet compliance demands amidst talent shortages."
                },
                {
                    "name": "SOC Manager",
                    "description": "Security Operations Center manager overseeing incident triage.",
                    "pain_points": [
                        "Extreme alert fatigue leading to missed critical threats",
                        "Severe shortage of skilled cybersecurity talent"
                    ],
                    "buying_triggers": [
                        "High analyst turnover",
                        "Audit finding showing slow mean-time-to-remediate (MTTR)"
                    ],
                    "objections": [
                        "System customization complexity",
                        "Disruption to established incident playbook workflows"
                    ],
                    "entry_content": "SOC Managers struggle with high alert volume and slow MTTR that leaves the business vulnerable."
                },
                {
                    "name": "Security Analyst",
                    "description": "Analyst triaging and investigating security logs and alerts.",
                    "pain_points": [
                        "Manually correlating logs across fragmented tools",
                        "High pressure to triage endless streams of low-fidelity alerts"
                    ],
                    "buying_triggers": [
                        "Need for automated playbooks",
                        "Desire to spend time on deep threat hunting"
                    ],
                    "objections": [
                        "AI generating false positives that waste analyst time",
                        "Interface complexity of security orchestration tools"
                    ],
                    "entry_content": "Security Analysts are burnt out by alert noise and manual log correlation across fragmented security tools."
                }
            ]
        },
        # 4. Strategic Portfolio Management (SPM)
        {
            "name": "Strategic Portfolio Management Messaging House",
            "summary": "This document covers buyer and user personas related to Strategic Portfolio Management, focusing on the roles involved in project portfolio planning and resource allocation.",
            "audience": "PMO, Finance, Operations",
            "brand_personality": "Strategic, structured, and insightful.",
            "positioning": "Aligning strategy with execution through AI-powered portfolio and resource management.",
            "tagline": "Connect business goals to execution and deliver value faster.",
            "differentiation": "ServiceNow's AI Agents dynamically predict resource bottlenecks and realign portfolios based on real-time execution data.",
            "personas": [
                {
                    "name": "VP of PMO",
                    "description": "Head of Project Management Office responsible for program delivery and strategic alignment.",
                    "pain_points": [
                        "Projects failing to deliver strategic business outcomes",
                        "Lack of visibility into project status and resource constraints"
                    ],
                    "buying_triggers": [
                        "Company-wide pivot to new strategic goals",
                        "Frequent project delays and budget overruns"
                    ],
                    "objections": [
                        "Skepticism about AI predicting project delivery risk",
                        "High cost of migrating legacy project data"
                    ],
                    "entry_content": "VPs of PMO struggle with lack of portfolio visibility and project delays that derail strategic goals."
                },
                {
                    "name": "Portfolio Manager",
                    "description": "Manager aligning resources and budgets across project streams.",
                    "pain_points": [
                        "Constant resource conflicts across competing business units",
                        "Manual data aggregation for monthly portfolio reviews"
                    ],
                    "buying_triggers": [
                        "Need to automate portfolio scenario planning",
                        "Inaccurate cost and budget forecasting"
                    ],
                    "objections": [
                        "Complexity of customizing workflow rules",
                        "User resistance to logging project updates in a new tool"
                    ],
                    "entry_content": "Portfolio Managers are overwhelmed by manual resource forecasting and constant budget conflicts."
                },
                {
                    "name": "Project Manager",
                    "description": "Lead executing individual projects and tracking tasks.",
                    "pain_points": [
                        "Chasing team members for status updates",
                        "Updating redundant spreadsheets and reporting tools"
                    ],
                    "buying_triggers": [
                        "Desire to automate status reporting",
                        "Need for real-time collaboration with cross-functional teams"
                    ],
                    "objections": [
                        "Extra administrative overhead of using a detailed PPM tool",
                        "Rigid project templates that don't fit agile workflows"
                    ],
                    "entry_content": "Project Managers waste significant time chasing team status updates and compiling manual reports."
                }
            ]
        },
        # 5. Asset Management
        {
            "name": "Asset Management Messaging House",
            "summary": "This document covers buyer and user personas related to Asset Management, focusing on hardware, software, and cloud asset tracking and lifecycle management.",
            "audience": "IT, Procurement, Finance",
            "brand_personality": "Precise, efficient, and cost-conscious.",
            "positioning": "Optimizing asset lifecycles and compliance through AI-driven tracking and cost analytics.",
            "tagline": "Track every asset, optimize spend, and eliminate audit risk.",
            "differentiation": "ServiceNow's AI Agents automatically identify software license reuse opportunities and reclaim unused cloud resources.",
            "personas": [
                {
                    "name": "VP of IT Infrastructure",
                    "description": "Leader managing data centers, cloud infrastructure, and enterprise hardware.",
                    "pain_points": [
                        "Uncontrolled cloud spend and license waste",
                        "Audit exposure and massive compliance fine risks"
                    ],
                    "buying_triggers": [
                        "Imminent vendor software audit",
                        "Corporate mandate to cut IT budget by 10%"
                    ],
                    "objections": [
                        "Implementation complexity in hybrid/multi-cloud environments",
                        "Potential downtime during agent deployment"
                    ],
                    "entry_content": "VPs of IT Infrastructure face high audit risks and waste due to unmanaged hardware and software assets."
                },
                {
                    "name": "IT Asset Manager",
                    "description": "Professional managing hardware/software compliance and lifecycles.",
                    "pain_points": [
                        "Manually tracking spreadsheets of assets across multiple sites",
                        "Siloed data between procurement and active inventory"
                    ],
                    "buying_triggers": [
                        "High rate of lost or unaccounted hardware",
                        "Upcoming software agreement renewals"
                    ],
                    "objections": [
                        "Difficulty in tracking legacy or off-network devices",
                        "Integration lag with existing procurement tools"
                    ],
                    "entry_content": "IT Asset Managers struggle with manual tracking spreadsheets and fragmented asset inventory systems."
                },
                {
                    "name": "Procurement Specialist",
                    "description": "Specialist purchasing hardware, software licenses, and cloud capacity.",
                    "pain_points": [
                        "Lack of usage data when negotiating renewals",
                        "Slow manual approval cycles delaying developer onboarding"
                    ],
                    "buying_triggers": [
                        "Need for automated software purchase approvals",
                        "Inefficient vendor contract management"
                    ],
                    "objections": [
                        "Clunky vendor catalogs",
                        "Loss of control over purchasing guardrails"
                    ],
                    "entry_content": "Procurement Specialists lack accurate asset usage data to negotiate cost-effective software renewals."
                }
            ]
        },
        # 6. Facilities & Workplace Service
        {
            "name": "Facilities & Workplace Service Messaging House",
            "summary": "This document covers buyer and user personas related to Facilities and Workplace Service, focusing on space planning and employee environment management.",
            "audience": "Facilities, HR, Operations",
            "brand_personality": "Supportive, welcoming, and organized.",
            "positioning": "Creating frictionless hybrid workspaces through automated facilities and space management.",
            "tagline": "Simplify workplace operations and elevate the employee experience.",
            "differentiation": "ServiceNow's AI Agents dynamically optimize office space usage and automate facilities maintenance dispatching.",
            "personas": [
                {
                    "name": "VP of Facilities",
                    "description": "Executive responsible for office real estate, safety, and workplace strategy.",
                    "pain_points": [
                        "Underutilized office spaces costing millions in lease waste",
                        "Difficulties in managing safety compliance for hybrid offices"
                    ],
                    "buying_triggers": [
                        "Transition to a hybrid work model",
                        "Real estate consolidation goals"
                    ],
                    "objections": [
                        "High upfront cost of IoT sensors and software",
                        "Long setup time for custom floor map designs"
                    ],
                    "entry_content": "VPs of Facilities face high real estate costs and underutilized office spaces in the hybrid work era."
                },
                {
                    "name": "Workplace Experience Manager",
                    "description": "Manager organizing office logistics, events, and daily operations.",
                    "pain_points": [
                        "Manual desk and room booking conflicts",
                        "Slow response times to employee workplace complaints"
                    ],
                    "buying_triggers": [
                        "Frequent complaints about meeting room availability",
                        "Inefficient visitor onboarding processes"
                    ],
                    "objections": [
                        "AI-based space allocation causing employee friction",
                        "Difficulty training non-technical staff"
                    ],
                    "entry_content": "Workplace Experience Managers struggle with manual booking conflicts and slow resolutions to office requests."
                },
                {
                    "name": "Facilities Technician",
                    "description": "Operative maintaining office hardware, HVAC, and facilities.",
                    "pain_points": [
                        "Unclear work order descriptions and incomplete repair details",
                        "Inefficient routing leading to wasted travel time between sites"
                    ],
                    "buying_triggers": [
                        "High volume of manual dispatch calls",
                        "Lack of mobile work order updates"
                    ],
                    "objections": [
                        "Clunky mobile app interfaces that drain battery",
                        "Fear of rigid tracking of response times"
                    ],
                    "entry_content": "Facilities Technicians lose productivity due to vague work orders and inefficient dispatch routing."
                }
            ]
        },
        # 7. Legal Service Delivery
        {
            "name": "Legal Service Delivery Messaging House",
            "summary": "This document covers buyer and user personas related to Legal Service Delivery, focusing on legal operations, contract management, and compliance requests.",
            "audience": "Legal, Compliance, Procurement",
            "brand_personality": "Rigorous, trustworthy, and efficient.",
            "positioning": "Accelerating business velocity through AI-powered legal operations and contract automation.",
            "tagline": "Automate routine legal tasks and protect the enterprise with speed.",
            "differentiation": "ServiceNow's AI Agents autonomously draft standard legal requests and triage complex compliance queries.",
            "personas": [
                {
                    "name": "General Counsel",
                    "description": "Chief legal officer managing enterprise legal risks and litigation.",
                    "pain_points": [
                        "Legal department seen as a bottleneck for sales deals",
                        "High risk of regulatory compliance misses due to manual review backlog"
                    ],
                    "buying_triggers": [
                        "Sales deal velocity slowing down due to NDA/contract review queues",
                        "Rapidly changing international data compliance laws"
                    ],
                    "objections": [
                        "Security and confidentiality of AI reviewing sensitive legal data",
                        "AI missing nuanced legal context in complex contracts"
                    ],
                    "entry_content": "General Counsel are frustrated when legal reviews become bottlenecks that slow down business deals."
                },
                {
                    "name": "Legal Operations Lead",
                    "description": "Manager optimizing legal processes, technology, and budget.",
                    "pain_points": [
                        "Inability to track legal request status and response metrics",
                        "High legal budget spent on routine outside counsel reviews"
                    ],
                    "buying_triggers": [
                        "Mandate to build a legal operations function",
                        "Spike in routine contract requests from sales"
                    ],
                    "objections": [
                        "High custom workflow setup cost",
                        "Difficulty integrating with corporate document repositories"
                    ],
                    "entry_content": "Legal Operations Leads struggle with zero visibility into request cycles and high spend on routine work."
                },
                {
                    "name": "Legal Assistant / Paralegal",
                    "description": "Frontline staff managing legal triage and filing.",
                    "pain_points": [
                        "Spending hours searching for historical contract templates",
                        "Answering the same basic legal process questions from internal teams"
                    ],
                    "buying_triggers": [
                        "Inability to handle volume of incoming NDA reviews",
                        "Desire to automate standard intake questionnaires"
                    ],
                    "objections": [
                        "AI tools replacing paralegal drafting roles",
                        "Complex formatting issues in AI-generated contracts"
                    ],
                    "entry_content": "Legal Assistants waste time on repetitive document intake and answering basic policy questions."
                }
            ]
        },
        # 8. Field Service Management
        {
            "name": "Field Service Management Messaging House",
            "summary": "This document covers buyer and user personas related to Field Service Management, focusing on scheduling, dispatching, and field technician operations.",
            "audience": "Operations, Support, Logistics",
            "brand_personality": "Reliable, practical, and responsive.",
            "positioning": "Optimizing field operations through AI-driven dispatching and mobile technician enablement.",
            "tagline": "Connect dispatch to the field and resolve issues on the first visit.",
            "differentiation": "ServiceNow's AI Agents dynamically schedule and route technicians based on real-time traffic and skills matching.",
            "personas": [
                {
                    "name": "VP of Field Operations",
                    "description": "Executive leading field service delivery, customer satisfaction, and fleet operations.",
                    "pain_points": [
                        "Low first-time fix rates driving up operational costs",
                        "Inability to track technician locations and job progress in real-time"
                    ],
                    "buying_triggers": [
                        "Rising customer complaints about missed appointment windows",
                        "Escalating technician travel and overtime costs"
                    ],
                    "objections": [
                        "Disruption to existing dispatcher-technician relationships",
                        "High cost of mobile device deployment and cellular packages"
                    ],
                    "entry_content": "VPs of Field Operations struggle with low first-time fix rates and rising fleet costs that hurt customer trust."
                },
                {
                    "name": "Dispatch Manager",
                    "description": "Operations supervisor planning schedules and assigning field tickets.",
                    "pain_points": [
                        "Manual schedule coordination when technicians call in sick",
                        "Wasted time manually matching technician skills to complex work orders"
                    ],
                    "buying_triggers": [
                        "Scheduling chaos during peak demand periods",
                        "High volume of phone calls to coordinate service visits"
                    ],
                    "objections": [
                        "AI systems overriding human judgment on local geography knowledge",
                        "System lag in updating schedules"
                    ],
                    "entry_content": "Dispatch Managers are overwhelmed by manual scheduling adjustments and skill-matching during peak demand."
                },
                {
                    "name": "Field Technician",
                    "description": "Mobile technician repairing equipment on-site at customer locations.",
                    "pain_points": [
                        "Arriving at site without the right parts or manual instructions",
                        "Wasting time writing manual paper reports after job completion"
                    ],
                    "buying_triggers": [
                        "Desire for mobile-first route guidance and parts ordering",
                        "Need for real-time remote support from senior engineers"
                    ],
                    "objections": [
                        "Feeling micro-managed by GPS tracking apps",
                        "Unreliable network coverage blocking mobile sync"
                    ],
                    "entry_content": "Field Technicians lose efficiency when they arrive on-site without correct parts or easy reporting tools."
                }
            ]
        },
        # 9. Financial Operations (FinOps)
        {
            "name": "Financial Operations Messaging House",
            "summary": "This document covers buyer and user personas related to Financial Operations, focusing on cloud cost optimization and financial approval workflows.",
            "audience": "Finance, DevOps, IT",
            "brand_personality": "Analytical, efficient, and proactive.",
            "positioning": "Optimizing cloud budgets and spend management through AI-driven FinOps analytics.",
            "tagline": "Unite finance and engineering to eliminate cloud waste.",
            "differentiation": "ServiceNow's AI Agents automatically identify cloud idle resources and orchestrate approval-free engineering reclaims.",
            "personas": [
                {
                    "name": "VP of Finance",
                    "description": "Financial leader managing budgets, forecasting, and operational margins.",
                    "pain_points": [
                        "Unpredictable and ballooning monthly public cloud bills",
                        "Lack of clear cost attribution to business departments"
                    ],
                    "buying_triggers": [
                        "Cloud bill exceeding budget by 20% in a single quarter",
                        "Board demands to improve SaaS gross margins"
                    ],
                    "objections": [
                        "Engineering teams ignoring cost recommendations",
                        "High software cost of FinOps platforms"
                    ],
                    "entry_content": "VPs of Finance are frustrated by unpredictable cloud bills and lack of cost attribution to departments."
                },
                {
                    "name": "FinOps Lead",
                    "description": "Dedicated professional managing cost allocation and cloud efficiency.",
                    "pain_points": [
                        "Difficulty getting developers to act on cloud optimization recommendations",
                        "Manual compilation of tag compliance reports across AWS, Azure, and GCP"
                    ],
                    "buying_triggers": [
                        "Wasteful over-provisioning of dev environments",
                        "Complex multi-cloud billing structures"
                    ],
                    "objections": [
                        "FinOps platforms adding security risk to cloud infrastructure",
                        "Inaccurate cost forecasting models"
                    ],
                    "entry_content": "FinOps Leads struggle to motivate development teams to act on cloud optimization recommendations."
                },
                {
                    "name": "Cloud Engineer",
                    "description": "Developer / DevOps engineer building infrastructure in the cloud.",
                    "pain_points": [
                        "Finance processes slowing down developer provisioning speeds",
                        "Cost optimization tasks getting in the way of shipping features"
                    ],
                    "buying_triggers": [
                        "Need for automated rightsizing tools in CI/CD pipeline",
                        "Desire to understand budget impacts of infrastructure choices"
                    ],
                    "objections": [
                        "Automated cost-cutting breaking production services",
                        "Clunky cost-tracking dashboards"
                    ],
                    "entry_content": "Cloud Engineers are slowed down by manual budget approval processes that delay infrastructure setup."
                }
            ]
        },
        # 10. Procurement Service Delivery
        {
            "name": "Procurement Service Delivery Messaging House",
            "summary": "This document covers buyer and user personas related to Procurement Service Delivery, focusing on vendor onboarding, purchasing, and sourcing workflows.",
            "audience": "Procurement, Supply Chain, Finance",
            "brand_personality": "Compliant, streamlined, and collaborative.",
            "positioning": "Streamlining corporate purchasing through automated intake and AI-guided sourcing.",
            "tagline": "Simplify buying processes and secure vendor compliance at scale.",
            "differentiation": "ServiceNow's AI Agents autonomously guide employees through purchasing rules, resolving intake errors before they reach buyers.",
            "personas": [
                {
                    "name": "Chief Procurement Officer",
                    "description": "Executive leader managing vendor spend, compliance, and sourcing strategies.",
                    "pain_points": [
                        "High rate of maverick (unapproved) spend outside contracts",
                        "Slow vendor onboarding times delaying key business projects"
                    ],
                    "buying_triggers": [
                        "Audit finding showing non-compliant vendor contracts",
                        "Need to scale procurement operations without adding headcount"
                    ],
                    "objections": [
                        "Employees bypassing the system because it is too complex",
                        "Long integration times with ERP systems like SAP"
                    ],
                    "entry_content": "CPOs struggle with high rates of maverick spend and slow vendor onboarding that stalls business operations."
                },
                {
                    "name": "Procurement Manager",
                    "description": "Operations supervisor managing buying queues and vendor selections.",
                    "pain_points": [
                        "Manually reviewing incomplete purchase requisitions",
                        "Delays in security and risk reviews for new vendors"
                    ],
                    "buying_triggers": [
                        "Procurement staff overwhelmed by emails and chat purchase requests",
                        "Bottlenecks in vendor risk assessments"
                    ],
                    "objections": [
                        "AI buying recommendations causing compliance issues",
                        "User adoption issues with complex sourcing templates"
                    ],
                    "entry_content": "Procurement Managers are bogged down by incomplete intake forms and slow manual risk reviews."
                },
                {
                    "name": "Buyer",
                    "description": "Professional negotiating deals and raising purchase orders (POs).",
                    "pain_points": [
                        "Manually entering PO details from emails into ERP systems",
                        "Dealing with constant vendor questions on payment status"
                    ],
                    "buying_triggers": [
                        "Desire to automate low-value PO routing",
                        "Need for centralized negotiation dashboards"
                    ],
                    "objections": [
                        "ERP system sync errors causing delays",
                        "Fear of automated purchasing removing vendor negotiation opportunities"
                    ],
                    "entry_content": "Buyers waste time on repetitive data entry into ERP systems and managing basic vendor status queries."
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
