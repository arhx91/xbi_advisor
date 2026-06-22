Please generate a detailed recommendation for the company in the following structure.

- Everything should be running text unless specified differently.
- Follow the order of this template.
- Maintain a balance of friendliness and professionalism throughout, while showing that Xebia is an authority in the field of data.
- Eliminate excessive adjectives.
- Never use dashes (-) in the narrative sense. You can still use them for bullet points.
- Make important concepts bold throughout the whole text.
- Don't make text unnecessarily long. Try to be as objective as possible, without removing any important details.
- Section 5. Cost Analysis should be copied exactly as is.

Start with (in header 4, so ###): Hello {{ name }} of {{ company_name }}, thank you for contacting us and filling in our questionnaire.
This personalised report is based on the questionnaire you have just filled in, which was carefully crafted by our team to reflect the most important aspects regarding your BI infrastructure. Our proprietary rules engine assigned scores against your responses to the three major BI tools (PowerBI, Tableau, Looker) based on our years of experience working with these tools. The LLM then translated our logic into a clear, readable format tailored specifically to your situation. Enjoy reading your report!

Second paragraph (not in bold): Add the key takeaways from the recommendation: at least one should be about their opportunties and/or risks and one about the BI tool we recommend for them and why. The tone should not be overly promotional. These should NOT be in bullet points.

## Executive Summary

### Opportunities and Risks

Add a table for opportunities and risks. Under Opportunities, add a list of bullet points that define the opportunities related to the current set up. This should summarise the following: Describe how the client's challenges are not simply linked to their BI tools, but also how data is governed and managed within their organization. These should not be displayed in bold.
Under Risks, add a list of bullet points that define the risks related to the current set up. These should not be displayed in bold. The table should look like this:

```markdown
| Opportunities           | Risks         |
| ----------------------- | ------------- |
| ----------------------- | ------------- |
| ----------------------- | ------------- |
| ----------------------- | ------------- |
| ----------------------- | ------------- |
```

Under the table, add a box that starts with "Advice: ". Follow this with one sentence that provides (practical) advice that would help them succeed regarding: performance, governance, scalability, adoption, and change management. Suggest actions the client needs to take before choosing a BI tool—such as defining governance, architecting a data environment, automating data pipelines, and implementing access management—to ensure a more fruitful BI investment. The box should look like this:

```markdown
<div class="info-box">

This is an info box with special styling.

</div>
```

### BI Tool Comparison

Please fill in the following table, which consists of four columns (the 'Category', 'Power BI', 'Tableau', and 'Looker'). Ensure the format is suited for Markdown. It should include five rows for each category, with scores for 'Power BI', 'Tableau', and 'Looker' for each one. Use the final ultimate row as a total summary by adding up each category's cumulative score.

The table should look EXACTLY as follows:

```markdown
| Category        | Power BI | Tableau | Looker  |
| --------------- | -------- | ------- | ------- |
| Ecosystem       | ...      | ...     | ...     |
| Security        | ...      | ...     | ...     |
| Data governance | ...      | ...     | ...     |
| Maturity level  | ...      | ...     | ...     |
| Capabilities    | ...      | ...     | ...     |
| **Total**       | **...**  | **...** | **...** |
```

Add one paragraph that explains which tool has the highest score and why. Briefly explain where the other tools might be stronger. This should be in a box that looks as such:

```markdown
<div class="info-box">

This is an info box with special styling.

</div>
```

## Detailed Analysis

### 1. Current Landscape: Where You Stand

Add the table below, which consists of two columns. For each category (e.g. current BI tool), add the relevant response from the respondent's replies. Maturity level, data governance and version control should be represented by a score from 1-5, with 5 being most mature. Replace the "X" in the X/5 below with the relevant score and visualise them in a nice way. Do not display any text in the table in bold.
Below the table, add a key finding of the current set-up (in bold).

The table should look EXACTLY as follows, with the two columns having approximately the same width:

```markdown
| Current Set-Up                      | Assessment |
| ----------------------------------- | ---------- |
| Current BI tool                     | ...        |
| Ecosystem                           | ...        |
| Data governance and version control | X/5        |
| Maturity level                      | X/5        |
| Visualisation requirements          | ...        |
| Current challenges                  | ...        |
```

### 2. Strategic Advice: What This Means for Your Business

#### Opportunities and Risks Ahead

Using the challenges, define potential pitfalls & opportunities for the client. Describe how the client's challenges are not simply linked to their BI tools, but also how data is governed and managed within their organization. Use around 200 words.

#### Future Scenarios: Action vs. Inaction

Paragraph explaining why these challenges matter. Provide (practical) advice that would help them succeed regarding: performance, governance, scalability, adoption, and change management. Suggest actions the client needs to take before choosing a BI tool—such as defining governance, architecting a data environment, automating data pipelines, and implementing access management—to ensure a more fruitful BI investment. Use around 200 words.

### 3. Exploring BI Options

Add: "Now that we've covered what you need to do, let's check some BI tool options and how they fit with your set-up."

#### BI Tool Comparison

Paragraph on the pros and cons of Power BI based on Rules Used. Don't add the rules names.

Paragraph on the pros and cons of Tableau based on Rules Used. Don't add the rules names.

Paragraph on the pros and cons of Looker based on Rules Used. Don't add the rules names.

Add: "The subsequent table offers a side-by-side comparison of Power BI, Tableau, and Looker, following a set of rules specifically defined by our team:"

Please fill in the following table, which consists of four columns (the 'Category', 'Power BI', 'Tableau', and 'Looker'). Ensure the format is suited for Markdown. It should include five rows for each category, with scores for 'Power BI', 'Tableau', and 'Looker' for each one. Use the final ultimate row as a total summary by adding up each category's cumulative score.

The table should look EXACTLY as follows:

```markdown
| Category                                                        | Power BI | Tableau | Looker  |
| --------------------------------------------------------------- | -------- | ------- | ------- |
| Ecosystem (Fit with your existing tech stack and tools)         | ...      | ...     | ...     |
| Security (Row-level security and compliance capabilities)       | ...      | ...     | ...     |
| Data governance (Centralized governance & version control)      | ...      | ...     | ...     |
| Maturity level (Suitability for your team's skills & processes) | ...      | ...     | ...     |
| Capabilities (Real-time updates & report delivery)              | ...      | ...     | ...     |
| **Total**                                                       | **...**  | **...** | **...** |
```

Right underneath the table add the following as a SUBHEADER (###):

#### How We Calculate These Scores

Our scoring system evaluates each BI tool across five key categories, with different maximum point values based on the number and importance of criteria in each category. The scores are generated through a rules-based engine that matches your specific requirements—including your existing technology stack, security needs, team capabilities, governance maturity, and desired features—against predefined criteria.

Each rule in our system is triggered when your situation aligns with specific conditions. For example, using Microsoft Azure adds points to Power BI's ecosystem score, requiring advanced row-level security favors Looker, and having a code-first team benefits Looker's maturity score. When multiple rules match your situation, points accumulate to create a comprehensive evaluation.

The categories weight differently based on scope: **Ecosystem** reflects platform fit; **Security** addresses access controls; **Data governance** evaluates centralized management; **Maturity level** assesses team readiness and approach; and **Capabilities** encompasses features, visualizations, and pain point resolutions."

Then add in italic: "The scores serve as guidance to help you identify which tool may work best for your organization, rather than absolute facts. Each tool has unique strengths, and the right choice depends on your specific priorities and constraints."

In the end: evaluate their current tool setup (if existing) and recommend an alternative, note that for a final decision they should contact Xebia for an evaluation of their setup in more detail. The painpoints should be highlighted in this section and play an important role in the final decision. Be careful with favoring one tool heavily, instead state that each tool has the potential to fit into their environment and that Xebia can be contacted to see if they need futher evaluation.

### 4. How We Can Help You Succeed

#### Consulting

Based on their current or future BI stack, which Xebia services would be most valuable? Refer back to the advice given earlier. Start with something along the lines of ""Understanding your unique challenges and how they can be transformed into growth opportunities, here's how our services can provide a custom solution for your needs." Underscore how Xebia's services specifically address the challenges identified and the opportunities mentioned in the previous section.

Use the following setup. The bold parts need to stay bold. Use around 50 words per bullet point:

- **Scalability**: add explanation on how this could help the organization.
- **Data Quality**: add explanation on how this could help the organization.
- **Performance**: add explanation on how this could help the organization.
- **Data Governance**: add explanation on how this could help the organization.
- **AI Implementation**: add explanation on how Generative AI and Agentic AI could help the organization.

#### Academy

Mention that Xebia has a dedicated academy where we offer high-end trainings. Mention where the gaps are in knowledge/skills and then connect these to the relevant trainings. Add the links to the trainings, EXACTLY like this example: "[Power BI in a Day](https://academy.xebia.com/training/power-bi-in-a-day/)". All trainings should be mentioned. Mention that even though the academy doesn't offer trainings for tools other than Power BI, we can always make tailor made traiings. No bullet points can be used, everything needss to be one paragraph.

### 5. Cost Analysis

#### [Tableau](https://www.tableau.com/en-gb/pricing)

**Pricing Model**: Per-user licensing
**Considerations**: Higher entry price but scales well for organizations with many view-only users
**Annual Estimate** for the Enterprise edition for a 50-Person Organization (10 Creators, 15 Explorers, 25 Viewers): **~€36,900/year**

Tableau offers three editions to their users: Tableau (comprehensive software package), Enterprise (advanced software package) and Tableau+ (premium package). For the Tableau and Enterprise edition, the fees are available online. Every deployment requires at least one Creator. For exact pricing and more information on the different editions, we would like to refer you to Tableau's [website](https://www.tableau.com/en-gb/pricing).

```markdown
| User Type      | Viewer         | Explorer       | Creator         |
| -------------- | -------------- | -------------- | --------------- |
| **Tableau**    | €15 user/month | €42 user/month | €75 user/month  |
| **Enterprise** | €35 user/month | €70 user/month | €115 user/month |
```

#### [Power BI](https://www.microsoft.com/en-ie/power-platform/products/power-bi/pricing)

**Pricing Model**: Per-user licensing
**Considerations**: Most cost-effective for small to medium businesses, free version available for basic needs
**Annual Estimate** for 50-Person Organization with all Pro licenses: **~€7,860/year**
**Annual Estimate** for 50-Person Organization with mixed licenses (10 PPU, 40 Pro): **~€8.988/year**

Power BI offers four editions to their users: a free account, Power BI Pro, Power BI Premium per User and Power BI Embedded. Power BI Pro includes standard features and is available for €13.10/user/month. The Power BI Premium Per User (PPU) includes more advanced features and is available for €22.50/user/month. To view detailed pricing information and learn more about the various editions available, please visit their [website](https://www.microsoft.com/en-ie/power-platform/products/power-bi/pricing).

#### [Looker](https://cloud.google.com/looker/pricing)

**Pricing Model**: Platform-based with user components
**Considerations**: Higher entry point but potentially better value for organizations heavily invested in data culture
**Annual Estimate** for 50-Person Organization: According to [Explo](https://www.explo.co/blog/looker-pricing) a team with 50 users (40 Standard, 10 Developers) could be looking at $100,000+ (**€85,970**) per year

Looker pricing has two main components: platform pricing (the cost to run a Looker instance) and user pricing (the cost for licensing individual users to access the Looker platform). Prices are only available through a sales call, but online sources ([Coefficient](https://coefficient.io/looker-pricing) and [Luzmo](https://www.luzmo.com/blog/looker-pricing)) indicate Looker starts at $60,000 (**€51,570**) per year. Please consult Looker's [website](https://cloud.google.com/looker/pricing) for accurate cost information and additional details about their different product editions.

### 6. Your Next Step with Xebia

End with a brief message, and add the following text:
"By partnering with Xebia, we can help you overcome your BI challenges across governance, adoption, and scalability."
"Please [contact us here](https://xebia.com/about-us/contact/) here for more information."
