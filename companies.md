---
layout: page
title: Companies
permalink: /companies/
---

{% assign companies = site.companies | sort: 'ticker' %}

{% if companies and companies.size > 0 %}
<ul>
{% for c in companies %}
  <li>
    <strong><a href="{{ c.url | relative_url }}">{{ c.ticker }}</a></strong>
    {% if c.name %} — {{ c.name }}{% endif %}
    {% if c.category %}<br /><span class="small">{{ c.category }}</span>{% endif %}
    {% if c.updated %}<br /><span class="small">Updated: {{ c.updated }}</span>{% endif %}
  </li>
{% endfor %}
</ul>
{% else %}
<p class="small">No companies yet.</p>
{% endif %}
