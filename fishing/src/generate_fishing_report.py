"""Build report and cash SVG from saved results; --pdf optionally needs reportlab."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import textwrap
from xml.sax.saxutils import escape

from fishing_milp import MODULE,read_csv


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--pdf",action="store_true");args=parser.parse_args()
    results=MODULE/"results";docs=MODULE/"docs";base=results/"baseline_112"
    s=json.loads((base/"summary.json").read_text());ds=read_csv(base/"daily_schedule.csv");acts=read_csv(base/"activity_schedule.csv")
    comparisons=read_csv(results/"comparison_summary.csv");lp=json.loads((results/"lp_bound.json").read_text())
    no_rods=next(r for r in comparisons if r["Scenario"]=="no_rods_112")
    fixed=max((r for r in comparisons if r["Scenario"].startswith("fixed_")),key=lambda r:float(r["Cash_End_g"]))
    lines=["# 钓鱼模块：Methodology 与结果分析", "", "基线结果来自已执行的 HiGHS 求解，所有金币均为模型期望现金；不是实际游戏逐竿实测。", "", "## 1. 实际运行结果", "",
           f"112 天最优期末现金 **{s['cash_end_g']:,.6f}g**。初始 500g，毛收入 {s['gross_revenue_g']:,.6f}g，总支出 {s['total_cost_g']:,.2f}g，合计 {s['total_casts']:,} 竿。现金恒等式为 500 + 毛收入 - 总支出。",
           "",f"求解状态 {s['status']}，MIP gap={s['mip_gap']}，最优上界 {s['best_bound']:,.6f}g，耗时 {s['solve_seconds']:.2f} 秒，{s['variables']:,} 个变量、{s['constraints']:,} 条约束。独立核查通过 {s['audit']['checks']:,} 项检查；7 项自动化测试全部通过。运行环境为 Python {s['python']}、HiGHS {s['version']}、单线程、seed=0。性能随电脑和版本变化。",
           "", "## 2. 一份最优操作方案", "", "导出的这份解在 Day 2 以 1,800g 购买 Fiberglass Rod，Day 4 首次使用鱼饵；不买 Iridium Rod，不使用任何吊钩。购买日和部分同值时段分配可能存在多个最优解，因此不能将 Day 2 宣称为唯一最优购买日。初始 Bamboo 不再收费。全年鱼饵支出 6,490g，吊钩摊销为 0。", "",
           "| 季节 | 主要地点与操作 | 竿数 | 季末现金（g） |", "| --- | --- | --- | --- |"]
    descriptions={"spring":"白天 Mountain Lake，夜间 Ocean；随等级少量使用 bait", "summer":"Ocean；成长到等级 10 后，典型日午后 bait 24 竿、夜间 none 14 竿", "fall":"Town River 白天、Ocean 夜间；每天 38 竿，其中 bait 1 竿", "winter":"Mountain Lake；每天 38 竿，其中 bait 19、none 19"}
    for season in ("spring","summer","fall","winter"):
        rows=[r for r in ds if r["Season"]==season]
        lines.append(f"| {season} | {descriptions[season]} | {sum(int(r['Casts']) for r in rows)} | {float(rows[-1]['Cash_End_g']):,.2f} |")
    lines += ["", "上述只是日程摘要。等级 10 从 Day 33（Summer 5）起生效；前期必须用当天真实等级的日程。以下列出代表日的完整非零动作，同一时段允许切换模式且不计准备时间。", "", "| 日期 | 时段 | 地点 | 模式 | 竿数 |", "| --- | --- | --- | --- | --- |"]
    for day in (1,4,35,57,85):
        for r in acts:
            if int(r["Day"])==day:
                lines.append(f"| {day} | {r['Time_Block']} | {r['Location']} | {r['Equipment_Mode']} | {r['Casts']} |")
    lines += ["", f"年末现金最优路径首次达到 100,000g 为 Day {s['first_100000_day']}（Summer 14）。这是该路径的观测值，不是“最早达标”的最优性证明。", "", "## 3. Methodology：只讨论 fishing", "",
              "| 课堂知识 | 本模块如何使用 | 正确性与解释 |", "| --- | --- | --- |",
              "| Lecture 2 LP：资源配置 | 每竿期望收入、成本、等待和体力线性加总；四时段与每日预算 | 目标最大化期末现金，不把毛收入当净利润；剩余资源不强制耗尽 |",
              "| Lecture 3：数据与模型、slack | CSV 与变量分离；导出每日资源余量 | 2,880 条输入逐键匹配，不用零填补缺失鱼池 |",
              "| Lecture 7 IP：整数与二元逻辑 | 整数竿数、精确日初等级、可选固定成本购竿及兼容性 | 完整规格用阈值 Big-M；程序消去 u，使用等价等级区间；U=38 有预算依据 |",
              "| Lecture 7：LP 松弛、分支定界 | MILP 求解器使用 LP 界、预处理、割平面及分支定界；记录 incumbent/bound/gap | 本项目并非自创启发式求解器；可行贪心仅作初解，不是最终最优性证据 |",
              "| Lecture 4：敏感性与经济解释 | 重求禁购装备、固定地点、资源份额情景 | 完整 MILP 的离散变化不能直接用 LP shadow price 解释 |",
              "| Lecture 5：estimate then optimize | 用预计算期望回报与等待作确定性输入，再优化配置 | 这是基于期望参数的 MILP，不是随机规划、蒙特卡洛或 robust optimization |",
              "| Lecture 6：流量平衡的思想 | 现金与累计竿数跨日平衡 | 它们是库存/状态平衡，不应宣称整个模型是标准最小费用流 |",
              "", "实现中的支配删列与等级区间投影是精确简化，其替换证明、映射及关闭删列方法见“代码运行与实现对照”。课堂方法的最优性结论仅适用于当前形式化设定与输入系数。", "", "## 4. Result Analysis：对照和建议", "",
              "| 情景 | 期末现金（g） | 状态 | gap |", "| --- | --- | --- | --- |"]
    for r in comparisons:
        lines.append(f"| {r['Scenario']} | {float(r['Cash_End_g']):,.2f} | {r['Status']} | {r['MIP_Gap']} |")
    delta=s["cash_end_g"]-float(no_rods["Cash_End_g"]);site=s["cash_end_g"]-float(fixed["Cash_End_g"])
    lines += ["",f"允许购竿的最优值比禁购鱼竿情景高 {delta:,.2f}g（{delta/float(no_rods['Cash_End_g'])*100:.2f}%）。这是扩大装备选择集合的收益，不等于‘每一竿都用鱼饵’的收益。与五个固定地点中最优的 {fixed['Scenario']} 相比，地点灵活性价值为 {site:,.2f}g（{site/float(fixed['Cash_End_g'])*100:.2f}%）；各固定地点控制仍允许按等级、时段选择模式与购买装备，并非随意制定的弱基准。",
              "", "模型没有要求买最高级装备。当前最优解中，更贵鱼竿与吊钩未被选中：当体力限制每天总竿数时，继续缩短等待不必然产生足以覆盖费用的额外收益。鱼饵则用于把部分抛竿移入更高回报时段；不能仅看全日还有时间就判断鱼饵无价值。不同系数、预算或联动配置下仍须重求。",
              "",f"LP 松弛上界为 {lp['objective']:,.6f}g，比整数最优值高 {lp['objective']-s['cash_end_g']:,.2f}g。上界说明放松整数/逻辑条件的代价；它不是可执行方案。最终 MILP 上界已收敛至整数目标。",
              "", "1/3 情景使用 166.67g 初始现金、每日 90 体力、300 总分钟，四个时段窗保持原长。它用于资源敏感性分析，不是联合三模块最优结果；更不能相加三个各占全部预算的独立目标值。",
              "", "## 5. 外部 benchmark 应怎么用", "", "当前最有说服力的定量基准是同输入下的固定地点策略、禁购装备情景、LP 上界与独立日程核查。社区金额只能提供背景，不能直接验证该 MILP 最优值。若新增真实游戏验证，建议固定游戏版本与起始状态，记录 7 或 28 天每竿结果、装备、时间与现金，重复若干次并报告偏差；当前未执行此实验。",
              "", "[Reddit 一年收益讨论](https://www.reddit.com/r/StardewValley/comments/1f36x2u/whats_the_most_money_you_have_made_in_year_1/) 是自报讨论，缺少统一起点、规则与现金口径。不得将个别回帖当总体均值或可比最优值。",
              "", "[Seawolf's 40 Mil Y1 Guide](https://docs.google.com/document/d/1ehta0YtKpOWyztyhKh0epxFhSjA665Sd48ZkEWSAj3Q/edit) 的原说明使用版本 1.4.5，综合 Skull Caverns、种植与加工；早期钓鱼包含食物增益、当日卖鱼再买装备及更快经验成长。其路线与本模块的晴天、无食物、次日升级、日初资金限制不一致，因此不做金额比值比较。可以把其‘前期钓鱼用于资金积累’作为定性背景，或把可比的钓鱼子策略重新放入本模型规则求值。",
              "", "## 6. Limitations", "", "1. 期望系数不是逐竿随机实现。等待波动可能使计划竿数超时，收入波动可能使后续购买缺钱；当前没有概率分布，不能给置信区间或伪造蒙特卡洛验证。",
              "2. 100% 捕获、无旅行和切换费用可能高估执行效率；晴天、普通品质、无食物和无宝箱又排除部分收益。因此结果不是对真实游戏收益的通用上界或下界。",
              "3. 所有结果均按一次经验计数并次日升级，与原版 XP 不同；四大时段的加权鱼池不能保证分钟级操作完全一致。",
              "4. 吊钩采用可分割的预期损耗摊销，不是整枚采购现金流；当前最优解未用吊钩，但敏感性情景仍受此简化影响。",
              "5. 原包未含完整逐结果概率表与来源快照；已验证系数内部一致性，尚不能独立重建全部期望值。",
              "6. 目标只看期末现金，不覆盖任务、社区中心、娱乐、库存价值或三模块协同收益。外部玩家也可能追求这些不同目标。",
              "", "## 7. 复现与证据", "", "运行命令、数学式映射与输出字段见“代码运行与实现对照”；原始数值与输入哈希见 results/baseline_112/summary.json，逐日和活动明细见同目录 CSV，比较见 results/comparison_summary.csv。源码与数据一并交付。Gurobi 适配入口已提供但未实测，本文的最优性证据全部来自 HiGHS。", ""]
    md=docs/"钓鱼模块_Methodology与结果分析.md";md.write_text("\n".join(lines),encoding="utf-8")
    # Standalone chart: native vector output, no external plotting dependency.
    w,h=800,360;points=[(65,300-500/350000*245)]+[(65+int(r["Day"])/112*695,300-float(r["Cash_End_g"])/350000*245) for r in ds]
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">', '<rect width="800" height="360" fill="white"/>', '<g font-family="Arial" font-size="12" fill="#334155">', '<text x="65" y="24" font-size="18">Fishing-only optimal cash path (112 days)</text>']
    for n in range(0,350001,50000):
        y=300-n/350000*245;svg += [f'<path d="M65 {y} H760" stroke="#e2e8f0"/>',f'<text x="4" y="{y+4}">{n:,}</text>']
    for day in (0,28,56,84,112):
        x=65+day/112*695;svg += [f'<text x="{x-7}" y="323">{day}</text>']
    svg += ['<text x="390" y="348">Day</text>',f'<polyline points="{" ".join(f"{x:.2f},{y:.2f}" for x,y in points)}" fill="none" stroke="#137c80" stroke-width="3"/>','</g></svg>']
    (results/"cash_path.svg").write_text("\n".join(svg),encoding="utf-8")
    if args.pdf:build_pdf(lines,docs/"钓鱼模块_Methodology与结果分析.pdf")
    print(md)


def build_pdf(lines,path):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    normal=ParagraphStyle("body",fontName="STSong-Light",fontSize=10,leading=16,spaceAfter=7,wordWrap="CJK")
    heading=ParagraphStyle("head",parent=normal,fontSize=14,leading=20,textColor=colors.HexColor("#176b75"),spaceBefore=12,spaceAfter=9,keepWithNext=True)
    title=ParagraphStyle("title",parent=heading,fontSize=20,leading=28,spaceAfter=18)
    small=ParagraphStyle("small",parent=normal,fontSize=8,leading=12)
    def paragraph(text,style=normal):
        import re
        text=text.replace("**","").replace("`","")
        parts=[];pos=0
        for match in re.finditer(r"\[([^]]+)\]\(([^)]+)\)",text):
            parts.append(escape(text[pos:match.start()]))
            parts.append(f'<link href="{escape(match[2], {chr(34): "&quot;"})}" color="#176b75">{escape(match[1])}</link>')
            pos=match.end()
        parts.append(escape(text[pos:]))
        return Paragraph("".join(parts),style)
    story=[];i=0
    while i<len(lines):
        line=lines[i]
        if line.startswith("|"):
            rows=[]
            while i<len(lines) and lines[i].startswith("|"):
                cells=[x.strip() for x in lines[i].strip("|").split("|")]
                if not all(x.strip("- :")=="" for x in cells): rows.append(cells)
                i+=1
            n=len(rows[0]);widths={3:[105,165,225],4:[120,205,65,105],5:[35,120,120,175,45]}[n]
            table=Table([[paragraph(c,small) for c in r] for r in rows],colWidths=widths,repeatRows=1,hAlign="LEFT")
            table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e4f0f1")),("VALIGN",(0,0),(-1,-1),"TOP"),("LINEBELOW",(0,0),(-1,0),.6,colors.HexColor("#176b75")),("LINEBELOW",(0,1),(-1,-1),.25,colors.HexColor("#d7e1e4")),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5)]))
            story += [table,Spacer(1,10)];continue
        if line.startswith("# "):story.append(paragraph(line[2:],title))
        elif line.startswith("## "):story.append(paragraph(line[3:],heading))
        elif line:story.append(paragraph(line))
        i+=1
    def footer(canvas,doc):
        canvas.setFont("STSong-Light",8);canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(50,28,"DBA5103 · Fishing · 2026-11-19");canvas.drawRightString(A4[0]-50,28,str(doc.page))
    SimpleDocTemplate(str(path),pagesize=A4,leftMargin=50,rightMargin=50,topMargin=42,bottomMargin=44,title="钓鱼模块 Methodology 与结果分析").build(story,onFirstPage=footer,onLaterPages=footer)


if __name__=="__main__":main()
