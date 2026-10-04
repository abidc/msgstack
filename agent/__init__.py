"""Conversational Slack/Teams agent for MsgStack — an MCP client, not a slash command.

Isolated from src/ on purpose: a parallel workstream is restructuring the
backend grounding model at the same time, and this package only ever talks
to it over HTTP (MCP + the review-log REST endpoint), never by importing
src.* directly.
"""
