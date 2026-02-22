# Director's Cut — 2-Minute Demo Script

**Target length:** ~2 minutes (~280 words at normal pace)

---

## 1. Main App & Search (0:00–0:25)

> *[Show HomePage]*

"This is Director's Cut — an AI-powered movie analysis and alternate-ending creator. On the home page you can browse featured movies or search for any film."

> *[Type a search, e.g. "Inception"]*

"I'll search for a movie… and click into it."

> *[Click a movie card]*

---

## 2. Movie Analysis & Run Pipeline (0:25–0:45)

> *[Show AnalysisPage]*

"Here we see the movie analysis page. If the movie hasn't been prepared yet, we click **Run Pipeline**."

> *[Click Run Pipeline]*

"While it runs, let me show you what's happening behind the scenes."

---

## 3. Pipeline Architecture (0:45–1:15)

> *[Switch to pipeline flowchart image / docs/pipeline_architecture.html]*

"The pipeline has three phases. **Data ingestion:** we fetch metadata from OMDB, scrape user reviews from IMDb, and pull critic reviews from our database. **Processing:** we chunk the reviews, embed them into vectors, and use clustering — powered by Gemini — to group similar complaints into complaint clusters. **Plot and story:** we pull the plot from Wikipedia, then use **Gemini** to generate structured plot beats and character analyses, and finally create three **what-if suggestions** based on the top complaint clusters. Everything flows into Supabase and our vector store."

---

## 4. Analysis Features (1:15–1:30)

> *[Back to AnalysisPage — after pipeline completes]*

"Once the pipeline finishes, we get the expanded plot, plot beats, character breakdowns, and complaint clusters with example reviews. The what-if suggestions are AI-generated alternatives that address common audience complaints."

---

## 5. What-If Story Flow (1:30–1:50)

> *[Click a what-if suggestion → RewritePage]*

"Let's pick a what-if and create an alternate story. This uses **Gemini multi-agent** logic: each step returns a narrative plus three choices. You pick one, and the model continues the story. You can also use **Eleven Labs TTS** to hear the narrative read aloud. After four steps, we get the alternate ending."

> *[Complete story flow → EndingPage]*

---

## 6. Final Analysis & Save to Explore (1:50–2:00)

> *[Show EndingPage]*

"On the ending page we see the **theme coverage score** — how well our story addressed the complaint clusters — plus an evidence panel showing which clusters were addressed. Click **Save Ending** to store it, then **Explore Leaderboard** to see community endings ranked by votes."

> *[Click Save Ending → Explore]*

"And that's Director's Cut — from search to pipeline to story creation to community exploration."

---

## Quick Reference: Tech Callouts

| Moment | Technology |
|--------|------------|
| Pipeline clustering | Gemini (labels clusters) |
| Plot beats & characters | Gemini |
| What-if suggestions | Gemini |
| Story creation | Gemini multi-agent (4-step branching) |
| Narrative TTS | Eleven Labs |
| Storage | Supabase + Vector Store |
