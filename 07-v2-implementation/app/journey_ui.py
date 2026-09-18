"""One journey over existing forms. Moving nodes preserves established handlers."""
from pathlib import Path


def enhance_journey_ui(html):
    script = Path(__file__).with_name('journey_ui.js').read_text()
    style = '''<style>
.nav{display:none!important}[hidden]{display:none!important}
.journey-nav{margin:10px 0}.journey-nav summary{cursor:pointer;padding:10px 0;color:var(--muted)}.journey-links{display:flex;gap:6px;flex-wrap:wrap}
.journey-nav button{min-height:46px;border:1px solid var(--line);border-radius:12px;background:white;font-weight:700;color:var(--muted)}
.journey-nav button[aria-current=page]{background:var(--text);color:white}
.journey-page>.panel,.journey-page details>.panel,#setupContent>.panel{display:block}
.journey-page details{margin:12px 0}.journey-page summary{cursor:pointer;padding:12px 0;font-weight:700}
#setupSteps{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}#setupSteps span{padding:6px 10px;border-radius:20px;background:#eef2ff;font-size:13px}#setupSteps [aria-current=step]{background:#111827;color:white}
#setupActions{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}#setupActions button{flex:1}
#journeyWelcome h1{font-size:28px;letter-spacing:-.04em;margin:4px 0 12px}#journeyWelcome p{line-height:1.6}
.journey-page .checks,#setupContent .checks{flex-wrap:wrap}#athleteDays{flex-wrap:wrap}
.journey-choice{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:16px 0}.journey-choice button{padding:18px;text-align:left;line-height:1.5;border:1px solid var(--line);border-radius:14px;background:white}.journey-choice button[aria-pressed=true]{border:2px solid var(--accent);background:#eff6ff}
#journeyMessage{color:var(--bad)}button:focus-visible,summary:focus-visible{outline:3px solid #60a5fa;outline-offset:3px}
@media(max-width:480px){.journey-choice{grid-template-columns:1fr}.grid{grid-template-columns:1fr}.keyrow{flex-wrap:wrap}.keyrow input{min-width:0;width:100%}}
</style>'''
    return html.replace('</head>', style+'</head>', 1).replace('</body>', '<script>'+script+'</script></body>', 1)
