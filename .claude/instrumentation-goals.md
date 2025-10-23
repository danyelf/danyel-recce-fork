These are some of the questions that I want to be able to answer with analytics instrumentation.

For each of these broad topics, I've written down first a broad theme ("I would like to ...") and an actionable outcome that I plan to use it for, then a couple of specific questions. All of these are based on the recce UI or the recce backend / API.

- Configuration

    “I would like to be able to know how many of our users are getting full value out of the app. How many of them are actually using the app, in which mode? Cloud, PR, and with/without database?

    This is actionable because I plan to use this to figure out where people are getting stuck, and which value we aren’t necessarily showing.*

    For example: do we have a large number of users drawing only the lineage, without seeing the comparison?

    Some of the more detailed questions:
        - Is there a cloud? is there a PR? Is there data?
        - Recency of the PR. Recency of the *.json files

- Dataset specs

    “I would like to know how big a change is, and how big datasets are. When we’re designing checklists, should we be thinking about tens of changes, or hundreds of changed tables? Similarly, number of added / removed columns; and — for each table — whether there’s a code change, or whether it’s just propagated-forward *s. The concrete outcomes I care about are saying in a conversation:

        - “when we’re designing for the checklist, we should think about how the user is going to deal with 100 changed models”
        - “is there  a way that a user can find themselves on a map of 100 models, where only one was changed?”

    - How *big and how much* of a dataset did the user have?
    - How many nodes, by each type (gold, silver, green -- corresponding to changed, unchanged, and added)?
    - How many columns, by each type (changed, unchanged, added, removed), and which are propoagated vs code-changed?

- User Interaction

    “I am generally trying to understand how people use the app -- virtually every button should come with some degree of instrumentation. In particular, I'm curious about people actually move between different modes? Can we figure out what cues they’re following as they move through lineage views? I also want to know about people's use of tools: Can we make guesses about people’s use of (e.g.) column-level diff, profile, etc? Which are most popular, or least? Can we correlate these with hypotheses about changed data, new columns, etc?”

    Design goal: look for bumps in the various paths, figure out what an analysis process looks like. Use qualitative analysis to watch users working with their data (thanks, replay recording)

- Collaboration

    *“How often do different people look at the same dataset? How often do they get there independently  — by coming from a PR or some similar structure — vs from our “share” button? Do we see people failing in the Share funnel by (e.g.) declining to create a cloud account to share, or to be shared?”*

    *Design goal: What can we do to support collaboration? Track improvements in uptake when we deploy things like Slack unfurls or other collaboration features. Track funnel drop-off at different stages.*

- Checklists

    *“What are the good/bad parts of checklists?”*“

    *how often do people add to a checklist?*

    *how often do they save a check off a checklist?*

    *“How often do people actually create a new checklist entry? how often do they share it?”*
