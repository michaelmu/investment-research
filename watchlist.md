---
layout: page
title: Watchlist
permalink: /watchlist/
---

**Not financial advice.**

{% assign items = site.data.investing_watchlist.items | sort: 'ticker' %}

{% if items and items.size > 0 %}
<ul>
{% for it in items %}
  <li>
    <strong>{{ it.ticker }}</strong>{% if it.name %} — {{ it.name }}{% endif %}
    {% if it.note %}<br />{{ it.note }}{% endif %}
    {% if it.tags %}<br /><em>tags:</em> {{ it.tags | join: ", " }}{% endif %}
  </li>
{% endfor %}
</ul>
{% else %}
No watchlist items yet.
{% endif %}
