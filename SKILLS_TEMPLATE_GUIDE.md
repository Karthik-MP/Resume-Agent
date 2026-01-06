# Skills & Projects Template Guide

## Overview
The resume agent now uses an LLM to generate both the skills and projects sections based on customizable LaTeX templates. This allows you to:
- Change the format without modifying code
- Customize categories and structure
- Control the exact LaTeX output
- Tailor content to job descriptions automatically

## Template Locations
Templates are located at:
- Skills: `SWE_Resume_Template/templates/skills_format.tex`
- Projects: `SWE_Resume_Template/templates/projects_format.tex`

## How It Works

### 1. Template Format
The template uses placeholder text `<comma-separated list>` that the LLM will replace with actual skills:

```latex
%-----------PROGRAMMING SKILLS-----------%
\section{Technical Skills}
    \begin{itemize}[leftmargin=0.05in, label={}]
	\small{\item{
		\textbf{Languages}{: <comma-separated list>} \\
		\textbf{Technologies}{: <comma-separated list>} \\
		\textbf{Tools \& Platforms}{: <comma-separated list>} \\
		\textbf{Certifications}{: <comma-separated list>}
	}}
    \end{itemize}
```

### 2. LLM Processing
When generating a resume:
1. The system loads your template
2. Selects relevant skills from `profile.json` based on:
   - Job description keywords
   - Selected projects' tech stacks
3. Sends to LLM with strict instructions to:
   - Output ONLY LaTeX
   - Follow the template structure exactly
   - Replace only the placeholder content
   - Use only provided skills (no fabrication)

### 3. Output
The LLM generates complete LaTeX matching your template:
```latex
%-----------PROGRAMMING SKILLS-----------%
\section{Technical Skills}
    \begin{itemize}[leftmargin=0.05in, label={}]
	\small{\item{
		\textbf{Languages}{: Python, JavaScript, Java} \\
		\textbf{Technologies}{: React.js, Node.js, FastAPI} \\
		\textbf{Tools \& Platforms}{: Docker, AWS, Git} \\
		\textbf{Certifications}{: Oracle Java SE Programmer}
	}}
    \end{itemize}
```

## Customizing the Template

### Change Categories
Edit `skills_format.tex` to add/remove/rename categories:

```latex
\textbf{Languages}{: <comma-separated list>} \\
\textbf{Frameworks}{: <comma-separated list>} \\
\textbf{Databases}{: <comma-separated list>} \\
\textbf{Cloud \& DevOps}{: <comma-separated list>} \\
\textbf{Soft Skills}{: <comma-separated list>}
```

### Change Format
You can modify the entire structure:

**Example: Two-column layout**
```latex
\section{Technical Skills}
    \begin{itemize}[leftmargin=0.05in, label={}]
	\small{\item{
		\begin{tabular}{ll}
			\textbf{Languages:} & <comma-separated list> \\
			\textbf{Frameworks:} & <comma-separated list> \\
		\end{tabular}
	}}
    \end{itemize}
```

**Example: Bullet-style skills**
```latex
\section{Technical Skills}
    \begin{itemize}
        \item \textbf{Languages:} <comma-separated list>
        \item \textbf{Technologies:} <comma-separated list>
    \end{itemize}
```

### Important: Keep Placeholders
Always use `<comma-separated list>` or similar clear placeholders where skills should go. The LLM is instructed to replace these.

## Updating profile.json

Make sure your `profile.json` has skills organized by the categories you use in the template. The category names should match or be mappable:

```json
{
  "skills": {
    "Languages": ["Python", "Java", "JavaScript"],
    "Technologies": ["React.js", "Node.js", "Docker"],
    "Tools & Platforms": ["Git", "AWS", "Linux"]
  },
  "certifications": [
    "Oracle Java SE Programmer",
    "Data Visualization",
    "Python",
    "Google Digital Marketing"
  ]
}
```

### Certifications
- Add certifications as a top-level array in `profile.json`
- **All certifications are always included** in the resume, regardless of job description relevance
- This ensures important credentials are never filtered out

### Category Mapping
The system uses fuzzy matching:
- "Web & Backend" in profile.json → "Technologies" in template
- "Cloud & DevOps" in profile.json → "Tools & Platforms" in template
- "Tools & Platforms" in profile.json → "Tools & Platforms" in template

## Configuration

### LLM Model
Set environment variable to change the model:
```bash
export OPENAI_MODEL="gpt-4"  # or "gpt-3.5-turbo", "gpt-4-turbo", etc.
export LLM_TEMPERATURE="0.1"  # Lower = more consistent output
```

### API Key
Ensure you have OpenAI API key set:
```bash
export OPENAI_API_KEY="your-api-key-here"
```

## Fallback Behavior
If LLM generation fails (no API key, network error, etc.), the system falls back to:
- Direct regex replacement of skills in existing LaTeX
- Less flexible but reliable

## Tips for Best Results

1. **Keep template simple**: Complex LaTeX structures may confuse the LLM
2. **Clear placeholders**: Use obvious placeholder text like `<list>` or `<skills>`
3. **Consistent formatting**: Use the same pattern for all categories
4. **Test changes**: Run the pipeline after template modifications to verify output
5. **Check logs**: The system logs whether LLM generation succeeded or used fallback

## Troubleshooting

### Skills not appearing
- Check that category names in template match those in `profile.json`
- Verify skills are actually relevant to the job description
- Ensure skills are part of selected projects' tech stacks

### Wrong format in output
- Review the template for syntax errors
- Check if LLM is hallucinating structure (try lowering temperature)
- Verify the regex pattern in graph.py matches your template's structure

### LLM not being called
- Check for error messages in logs
- Verify OPENAI_API_KEY is set
- Ensure langchain-openai is installed

## Future Extensions

You can create additional templates:
- `templates/experience_format.tex` - Work experience format
- `templates/education_format.tex` - Education section format

To use them, add similar LLM generation logic in the appropriate section of `graph.py`.

---

## Projects Section

### How It Works

The projects section follows the same LLM-based generation approach:

1. **Template Format** (`projects_format.tex`):
```latex
%-----------PROJECTS-----------%
\section{Projects}
\resumeSubHeadingListStart

    \resumeProjectHeading
    {\textbf{<Project Name>} $|$ \emph{<Tech Stack>}}{}
    \resumeItemListStart
        \resumeItem{<STAR bullet point 1>}
        \resumeItem{<STAR bullet point 2>}
    \resumeItemListEnd

    \resumeProjectHeading
    {\textbf{<Project Name>} $|$ \emph{<Tech Stack>}}{}
    \resumeItemListStart
        \resumeItem{<STAR bullet point 1>}
        \resumeItem{<STAR bullet point 2>}
    \resumeItemListEnd

\resumeSubHeadingListEnd
```

2. **LLM Processing**:
   - Selects top 2 most relevant projects from `profile.json` based on JD keywords
   - Loads project data (name, tech stack, description, metrics)
   - Sends to LLM with instructions to:
     - Write in STAR format (Situation-Task-Action-Result)
     - Start with action verbs (Developed, Engineered, Built, etc.)
     - Include quantifiable metrics
     - Tailor to job description keywords
     - Generate exactly 2 projects with 2-3 bullets each

3. **Output**:
   - Complete LaTeX matching your template
   - Professionally written, job-tailored project descriptions
   - Metrics and results highlighted

### Customizing Projects Template

**Add project links:**
```latex
\resumeProjectHeading
{\href{<GitHub URL>}{\textbf{<Project Name>}} $|$ \emph{<Tech Stack>}}{}
```

**Change bullet style:**
```latex
\resumeItemListStart
    \item <STAR bullet point 1>
    \item <STAR bullet point 2>
\resumeItemListEnd
```

**Add date/duration:**
```latex
\resumeProjectHeading
{\textbf{<Project Name>} $|$ \emph{<Tech Stack>}}{<Start Date -- End Date>}
```
