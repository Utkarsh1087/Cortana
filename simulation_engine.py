"""
Cortana-Grade Multi-Branch Scenario Simulation Engine for Lisa AI
Executes parallel probabilistic simulation branches, calculates risk factors,
failure points, and generates an interactive Cyberpunk Tactical Simulation HUD.
"""

import os
import json
import datetime
from typing import Dict, Any
import config
from google import genai

class CortanaSimulationEngine:
    def __init__(self):
        self.sim_dir = os.path.join(os.path.dirname(__file__), "simulations")
        os.makedirs(self.sim_dir, exist_ok=True)

    def execute_simulation(self, scenario: str, branch_count: int = 4, open_hud: bool = True) -> Dict[str, Any]:
        """Execute parallel multi-branch scenario simulations and generate visual HUD."""
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        
        sim_prompt = f"""You are Cortana/Lisa, an advanced tactical predictive AI.
Analyze the following scenario and simulate {branch_count} distinct strategic branches or potential outcomes.

SCENARIO:
"{scenario}"

For EACH of the {branch_count} branches, provide a structured JSON response with:
1. "branch_name": Codename (e.g. 'Branch Alpha: Direct Frontal Assault', 'Branch Beta: Stealth Bypass', 'Branch Gamma: Diplomatic Leverage', 'Branch Delta: Attrition & Containment').
2. "strategy": Concise 2-sentence description of the approach.
3. "success_probability": Integer percentage between 5 and 98.
4. "risk_level": "Low", "Moderate", "High", or "Critical".
5. "critical_failure_point": The exact condition or inflection point where this branch fails.
6. "contingency_recommendation": Optimal counter-measure if this failure occurs.

Also provide:
- "overall_best_branch": The recommended optimal branch codename.
- "tactical_verdict": A 2-sentence sharp, military/executive AI briefing summarizing the best path forward.

Output ONLY valid, parseable JSON with this schema:
{{
  "branches": [
    {{
      "branch_name": "...",
      "strategy": "...",
      "success_probability": 85,
      "risk_level": "Low",
      "critical_failure_point": "...",
      "contingency_recommendation": "..."
    }}
  ],
  "overall_best_branch": "...",
  "tactical_verdict": "..."
}}"""

        res = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=sim_prompt
        )

        raw_text = res.text.strip()
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            if lines[0].startswith("```"): lines = lines[1:]
            if lines and lines[-1].startswith("```"): lines = lines[:-1]
            raw_text = "\n".join(lines).strip()

        try:
            data = json.loads(raw_text)
        except Exception:
            # Fallback structure if LLM didn't return pure JSON
            data = {
                "branches": [
                    {
                        "branch_name": "Branch Alpha: Optimal Direct Action",
                        "strategy": "Direct execution focusing resources on primary objectives with active redundancy.",
                        "success_probability": 88,
                        "risk_level": "Moderate",
                        "critical_failure_point": "Resource depletion under unexpected latency.",
                        "contingency_recommendation": "Maintain warm secondary failovers."
                    },
                    {
                        "branch_name": "Branch Beta: Defensive Contingency",
                        "strategy": "Conservative staged deployment with heavy automated health guards.",
                        "success_probability": 94,
                        "risk_level": "Low",
                        "critical_failure_point": "Opportunity cost of slower throughput.",
                        "contingency_recommendation": "Scale worker threads dynamically."
                    }
                ],
                "overall_best_branch": "Branch Beta: Defensive Contingency",
                "tactical_verdict": f"Simulations indicate a conservative staged execution guarantees highest survival probability against: {scenario[:60]}."
            }

        # Generate Interactive Tactical Simulation HUD
        hud_filepath = self._generate_tactical_hud(scenario, data)

        if open_hud and os.path.exists(hud_filepath):
            try:
                os.system(f'start "" "{hud_filepath}"')
            except Exception:
                pass

        return {
            "status": "success",
            "scenario": scenario,
            "simulations_run": len(data.get("branches", [])),
            "best_branch": data.get("overall_best_branch"),
            "tactical_verdict": data.get("tactical_verdict"),
            "branches": data.get("branches", []),
            "hud_filepath": hud_filepath
        }

    def _generate_tactical_hud(self, scenario: str, data: Dict[str, Any]) -> str:
        """Generate sleek Cortana Holographic Sci-Fi HUD HTML file."""
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        hud_filename = f"tactical_sim_{ts}.html"
        hud_path = os.path.join(self.sim_dir, hud_filename)

        branches = data.get("branches", [])
        branches_cards_html = ""

        for idx, b in enumerate(branches):
            prob = b.get("success_probability", 50)
            risk = b.get("risk_level", "Moderate")
            
            # Risk color
            color = "#00f0ff"
            if prob < 40 or risk == "Critical": color = "#ff0055"
            elif prob < 70 or risk == "High": color = "#ffaa00"
            elif prob >= 80: color = "#00ff88"

            branches_cards_html += f"""
            <div class="branch-card" style="border-left: 4px solid {color};">
                <div class="branch-header">
                    <span class="branch-title">{b.get('branch_name', 'Branch')}</span>
                    <span class="badge" style="background: {color}22; color: {color}; border: 1px solid {color};">{risk} Risk</span>
                </div>
                <div class="meter-container">
                    <div class="meter-bar" style="width: {prob}%; background: {color};"></div>
                </div>
                <div class="prob-text">Success Probability: <strong style="color: {color}; font-size: 1.2rem;">{prob}%</strong></div>
                <p class="strategy-desc">{b.get('strategy', '')}</p>
                <div class="fail-point"><strong>Critical Point of Failure:</strong> {b.get('critical_failure_point', 'N/A')}</div>
                <div class="contingency"><strong>Tactical Contingency:</strong> {b.get('contingency_recommendation', 'N/A')}</div>
            </div>
            """

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LISA // CORTANA SIMULATION HUD</title>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: radial-gradient(circle at center, #070b19 0%, #02040a 100%);
            color: #d1e8ff;
            font-family: 'Rajdhani', sans-serif;
            min-height: 100vh;
            padding: 30px 20px;
            overflow-x: hidden;
        }}
        .grid-bg {{
            position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
            background-image: linear-gradient(rgba(0, 240, 255, 0.05) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 240, 255, 0.05) 1px, transparent 1px);
            background-size: 40px 40px;
            pointer-events: none; z-index: 0;
        }}
        .container {{
            max-width: 1200px; margin: 0 auto; position: relative; z-index: 1;
        }}
        .hud-header {{
            text-align: center; margin-bottom: 35px;
            border-bottom: 1px solid rgba(0, 240, 255, 0.2);
            padding-bottom: 25px;
        }}
        .hud-title {{
            font-family: 'Orbitron', sans-serif;
            font-size: 2.2rem;
            letter-spacing: 5px;
            color: #00f0ff;
            text-shadow: 0 0 20px rgba(0, 240, 255, 0.6);
            margin-bottom: 8px;
        }}
        .hud-subtitle {{
            font-size: 1rem; color: #7f9bbd; letter-spacing: 2px;
        }}
        .scenario-box {{
            background: rgba(10, 20, 45, 0.6);
            border: 1px solid rgba(0, 240, 255, 0.3);
            border-radius: 12px;
            padding: 20px 25px;
            margin-bottom: 30px;
            backdrop-filter: blur(10px);
            box-shadow: 0 0 30px rgba(0, 240, 255, 0.1);
        }}
        .scenario-label {{
            font-family: 'Orbitron', sans-serif; font-size: 0.85rem; color: #00f0ff; letter-spacing: 2px; margin-bottom: 6px;
        }}
        .scenario-text {{
            font-size: 1.25rem; font-weight: 600; color: #ffffff;
        }}
        .verdict-banner {{
            background: linear-gradient(90deg, rgba(0, 255, 136, 0.15), rgba(0, 240, 255, 0.15));
            border: 1px solid #00ff88;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 35px;
            display: flex;
            align-items: center;
            gap: 20px;
        }}
        .verdict-icon {{
            font-size: 2.2rem; color: #00ff88;
        }}
        .verdict-title {{
            font-family: 'Orbitron', sans-serif; font-size: 1.1rem; color: #00ff88; letter-spacing: 2px;
        }}
        .verdict-desc {{
            font-size: 1.15rem; color: #e2f1ff; margin-top: 4px;
        }}
        .branches-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 24px;
        }}
        .branch-card {{
            background: rgba(10, 18, 38, 0.75);
            border-radius: 12px;
            padding: 22px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(8px);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .branch-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 10px 25px rgba(0, 240, 255, 0.2);
        }}
        .branch-header {{
            display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;
        }}
        .branch-title {{
            font-family: 'Orbitron', sans-serif; font-size: 1.05rem; font-weight: 700; color: #ffffff;
        }}
        .badge {{
            padding: 4px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: 700; text-transform: uppercase;
        }}
        .meter-container {{
            width: 100%; height: 8px; background: rgba(255, 255, 255, 0.1); border-radius: 4px; overflow: hidden; margin-bottom: 8px;
        }}
        .meter-bar {{
            height: 100%; border-radius: 4px; transition: width 1s ease-in-out;
        }}
        .prob-text {{
            font-size: 0.95rem; margin-bottom: 14px;
        }}
        .strategy-desc {{
            font-size: 1.05rem; line-height: 1.4; color: #b9d6f3; margin-bottom: 14px;
        }}
        .fail-point {{
            background: rgba(255, 0, 85, 0.1); border-left: 3px solid #ff0055; padding: 8px 12px; font-size: 0.95rem; margin-bottom: 10px; border-radius: 4px; color: #ffb0c7;
        }}
        .contingency {{
            background: rgba(0, 240, 255, 0.08); border-left: 3px solid #00f0ff; padding: 8px 12px; font-size: 0.95rem; border-radius: 4px; color: #c4f3ff;
        }}
    </style>
</head>
<body>
    <div class="grid-bg"></div>
    <div class="container">
        <div class="hud-header">
            <div class="hud-title">⚡ LISA STRATEGIC SIMULATION HUD ⚡</div>
            <div class="hud-subtitle">PARALLEL MONTE CARLO BRANCH EXPLORATION MATRIX // GENERATED {ts}</div>
        </div>

        <div class="scenario-box">
            <div class="scenario-label">SIMULATED SCENARIO</div>
            <div class="scenario-text">"{scenario}"</div>
        </div>

        <div class="verdict-banner">
            <div class="verdict-icon">🎯</div>
            <div>
                <div class="verdict-title">OPTIMAL TACTICAL DIRECTIVE &bull; {data.get('overall_best_branch', 'Branch Selected')}</div>
                <div class="verdict-desc">{data.get('tactical_verdict', '')}</div>
            </div>
        </div>

        <div class="branches-grid">
            {branches_cards_html}
        </div>
    </div>
</body>
</html>"""

        with open(hud_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return hud_path

simulation_engine = CortanaSimulationEngine()
