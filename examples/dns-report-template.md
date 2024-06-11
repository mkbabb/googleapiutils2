{% markdown %}

# [{{filename}}]({{range_url}})

#### Analysis Using Nameserver: _{{ dns_info['NS'] }}_

-   SPF Enabled: **{{ YES_TAG if dns_info['Has SPF'] else NO_TAG }}**
-   DMARC Enabled: **{{ YES_TAG if dns_info['Has DMARC'] else NO_TAG }}**
-   DKIM Enabled: **{{ YES_TAG if dns_info['Has DKIM'] else NO_TAG }}**
-   MTA-STS Enabled: **{{ YES_TAG if dns_info['Has MTA-STS'] else NO_TAG }}**
-   BIMI Enabled: **{{ YES_TAG if dns_info['Has BIMI'] else NO_TAG }}**

{% if dns_info['Has SPF'] %}

### SPF IPs

{% for ip in dns_info['SPF IPs'] %}
-   {{ ip }}
{% endfor %}

{% endif %}

{% if dns_info['Has DMARC'] %}

### DMARC Record

{{ dns_info['DMARC Record'] }}

{% endif %}

{% if dns_info['Has DKIM'] %}

### DKIM Record

{{ dns_info['DKIM Record'] }}

{% endif %}

{% if dns_info['Has MTA-STS'] %}

### MTA-STS Record

{{ dns_info['MTA-STS Record'] }}

{% endif %}

{% if dns_info['Has BIMI'] %}

### BIMI Record

{{ dns_info['BIMI Record'] }}

{% endif %}

---

## DNS Records Analysis

### Summary

{{ dns_analysis.summary }}

### Potential Misconfigurations

{% for misconfig in dns_analysis.misconfigurations %}
-   {{ misconfig }}
{% endfor %}

### Recommendations

{% for recommendation in dns_analysis.recommendations %}
-   {{ recommendation }}
{% endfor %}

{% endmarkdown %}