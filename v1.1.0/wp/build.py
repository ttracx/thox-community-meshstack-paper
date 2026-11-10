"""Build the paper HTML from summary.json and the verified reference table.

Every number comes from exp/results/summary.json via the S dict. Citations are
[@key]; numbering is by first use. Run: python3 wp/build.py -> wp/paper.src.html
then node wp/katex_render.cjs wp/paper.src.html wp/paper.html.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S = json.loads((ROOT / "exp" / "results" / "summary.json").read_text())
REFS_RAW = json.loads((ROOT / "wp" / "refs_raw.json").read_text())
FIG = ROOT / "wp" / "figures"

VERSION = "v1.1.0"
DATE = "2026-11-10"
TITLE = "THOX Community Mesh: Unlinkable Subscriber Tokens, Digest-Audited Stage Execution and a Witness-Cosigned Settlement Ledger for Member-Contributed Inference"
SHORT = "THOX community mesh: member-contributed private inference"

# ----------------------------------------------------------------------------
# References. arXiv entries come verbatim from refs_raw.json (fetched from the
# arXiv export API on 2026-11-10). RFC entries were read from the RFC Editor's
# per-RFC JSON record the same day. Venue pages were opened live the same day
# and titles and authors copied from them.
# ----------------------------------------------------------------------------
MANUAL_REFS = {
    "rfc9474": {"authors": ["F. Denis", "F. Jacobs", "C. A. Wood"], "title": "RSA Blind Signatures", "venue": "RFC 9474, IRTF, October 2023", "url": "https://www.rfc-editor.org/rfc/rfc9474"},
    "rfc9576": {"authors": ["A. Davidson", "J. Iyengar", "C. A. Wood"], "title": "The Privacy Pass Architecture", "venue": "RFC 9576, IETF, June 2024", "url": "https://www.rfc-editor.org/rfc/rfc9576"},
    "rfc9578": {"authors": ["S. Celi", "A. Davidson", "S. Valdez", "C. A. Wood"], "title": "Privacy Pass Issuance Protocols", "venue": "RFC 9578, IETF, June 2024", "url": "https://www.rfc-editor.org/rfc/rfc9578"},
    "rfc9458": {"authors": ["M. Thomson", "C. A. Wood"], "title": "Oblivious HTTP", "venue": "RFC 9458, IETF, January 2024", "url": "https://www.rfc-editor.org/rfc/rfc9458"},
    "rfc9180": {"authors": ["R. Barnes", "K. Bhargavan", "B. Lipp", "C. Wood"], "title": "Hybrid Public Key Encryption", "venue": "RFC 9180, IRTF, February 2022", "url": "https://www.rfc-editor.org/rfc/rfc9180"},
    "rfc8032": {"authors": ["S. Josefsson", "I. Liusvaara"], "title": "Edwards-Curve Digital Signature Algorithm (EdDSA)", "venue": "RFC 8032, IRTF, January 2017", "url": "https://www.rfc-editor.org/rfc/rfc8032"},
    "rfc9162": {"authors": ["B. Laurie", "E. Messeri", "R. Stradling"], "title": "Certificate Transparency Version 2.0", "venue": "RFC 9162, IETF, December 2021", "url": "https://www.rfc-editor.org/rfc/rfc9162"},
    "sarmenta": {"authors": ["Luis F. G. Sarmenta"], "title": "Sabotage-Tolerance Mechanisms for Volunteer Computing Systems", "venue": "ACM/IEEE International Symposium on Cluster Computing and the Grid (CCGrid'01), Brisbane, May 2001", "url": "https://groups.csail.mit.edu/cag/bayanihan"},
    "drf": {"authors": ["Ali Ghodsi", "Matei Zaharia", "Benjamin Hindman", "Andy Konwinski", "Scott Shenker", "Ion Stoica"], "title": "Dominant Resource Fairness: Fair Allocation of Multiple Resource Types", "venue": "NSDI 2011", "url": "https://www.usenix.org/conference/nsdi11/dominant-resource-fairness-fair-allocation-multiple-resource-types"},
    "tor": {"authors": ["Roger Dingledine", "Nick Mathewson", "Paul Syverson"], "title": "Tor: The Second-Generation Onion Router", "venue": "13th USENIX Security Symposium, 2004", "url": "https://www.usenix.org/conference/13th-usenix-security-symposium/tor-second-generation-onion-router"},
    "pcc": {"authors": ["Apple Security Engineering and Architecture, User Privacy, Core Operating Systems, Services Engineering, and Machine Learning and AI"], "title": "Private Cloud Compute: A new frontier for AI privacy in the cloud", "venue": "Apple Security Research blog, 10 June 2024, accessed 2026-11-10", "url": "https://security.apple.com/blog/private-cloud-compute/"},
    "smollm": {"authors": ["Hugging Face TB Research"], "title": "HuggingFaceTB/SmolLM2-135M-Instruct model repository, revision 12fd25f7", "venue": "Hugging Face, accessed 2026-11-10", "url": "https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct"},
    "thoxP1": {"authors": ["Craig Ross", "Tommy Xaypanya"], "title": "THOX MeshStack: Capacity-Priced Pipeline Sharding, Grant-Gated KV Transfer and Lease-Fenced Device Roles for a Private Household Mesh", "venue": "THOX.ai Research technical report v1.0.1, 2026-11-03, Zenodo, doi:10.5281/zenodo.23919580", "url": "https://doi.org/10.5281/zenodo.23919580"},
    "thoxCC": {"authors": ["Craig Ross", "Tommy Xaypanya"], "title": "MeshStack Community Compute: Privacy governed shared hardware and distributed AI", "venue": "THOX.ai LLC research paper THOX-RP-COMMUNITY-2026-001, version 1.0, 10 November 2026, with the THOX MeshStack virtual lab v1.0 (confidential, prepared for author review; PDF SHA-256 e202e7d0...14fe)", "url": ""},
    "thoxRole": {"authors": ["THOX.ai"], "title": "Auto Device Role Mode (THOX-MESH-ROLE-001, version 0.1.1)", "venue": "ttracx/meshstack-backend, docs/auto-device-role-mode.md, 2026-11-02 (internal engineering preview)", "url": ""},
    "thoxDec": {"authors": ["THOX.ai"], "title": "Decisions of record D1 to D49", "venue": "ttracx/thox-meshstack-inference, DECISIONS.md, commit 7e86cec, read 2026-11-10 (internal)", "url": ""},
    "thoxSec": {"authors": ["THOX.ai"], "title": "Security model: KV cache, grants and the mesh", "venue": "ttracx/thox-meshstack-inference, docs/SECURITY.md, commit 7e86cec, read 2026-11-10 (internal)", "url": ""},
    "thoxADR": {"authors": ["THOX.ai"], "title": "ADR-025: Ollama Cloud tags are not local mesh compute", "venue": "ttracx/meshstack-desktop, docs/architecture_decisions.md, commit b2b6e3f, read 2026-11-10 (internal)", "url": ""},
}

CITED: list[str] = []



def ref_entry(key: str) -> dict:
    if key in REFS_RAW and REFS_RAW[key]["status"] == "resolved":
        r = REFS_RAW[key]
        return {"authors": r["authors"], "title": r["title"],
                "venue": f"arXiv:{r['arxiv_id']}, first posted {r['published'][:10]}, version inspected {r['updated'][:10]}" + (f"; {r['journal_ref']}" if r.get("journal_ref") else ""),
                "url": r["url"]}
    if key in MANUAL_REFS:
        return MANUAL_REFS[key]
    raise KeyError(f"unknown citation key {key}")


def cite(text: str) -> str:
    def repl(m):
        keys = [k.strip().lstrip("@") for k in m.group(1).split(";")]
        nums = []
        for k in keys:
            ref_entry(k)
            if k not in CITED:
                CITED.append(k)
            nums.append(str(CITED.index(k) + 1))
        return '<span class="cite">[' + ", ".join(nums) + "]</span>"
    return re.sub(r"\[@([^\]]+)\]", repl, text)


# ----------------------------------------------------------------------------
# HTML helpers
# ----------------------------------------------------------------------------
OUT: list[str] = []


def p(text: str):
    OUT.append(f"<p>{cite(text)}</p>")


def h2(num: str, text: str, anchor: str):
    OUT.append(f'<h2 id="{anchor}"><span class="num">{num}</span>{text}</h2>')


def h3(text: str):
    OUT.append(f"<h3>{text}</h3>")


def eq(tex: str, display: bool = True):
    OUT.append(f'<div class="eq"><span class="katex-src" data-display="{1 if display else 0}">{html.escape(tex)}</span></div>')


def ieq(tex: str) -> str:
    return f'<span class="katex-src" data-display="0">{html.escape(tex)}</span>'


def table(headers: list[str], rows: list[list[str]], caption: str = "", cls: str = ""):
    th = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{cite(c)}</td>" for c in r) + "</tr>" for r in rows)
    cap = f"<caption>{cite(caption)}</caption>" if caption else ""
    OUT.append(f'<table class="{cls}">{cap}<thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>')


def figure(svg: str, num: int, caption: str):
    content = (FIG / svg).read_text()
    content = re.sub(r"<\?xml[^>]*\?>", "", content)
    content = re.sub(r"<!DOCTYPE[^>]*>", "", content)
    OUT.append(f'<figure id="fig{num}"><div class="figwrap">{content}</div><figcaption><b>Figure {num}.</b> {cite(caption)}</figcaption></figure>')


def callout(title: str, body: str, kind: str = "note"):
    OUT.append(f'<div class="callout {kind}"><div class="ct">{title}</div><div>{cite(body)}</div></div>')


def algo(title: str, lines: list[str]):
    body = "\n".join(html.escape(l) for l in lines)
    OUT.append(f'<div class="algo"><div class="at">{title}</div><pre>{body}</pre></div>')


def ul(items: list[str]):
    OUT.append("<ul>" + "".join(f"<li>{cite(i)}</li>" for i in items) + "</ul>")


def ol(items: list[str]):
    OUT.append("<ol>" + "".join(f"<li>{cite(i)}</li>" for i in items) + "</ol>")


def fmt(x: float, nd: int = 2) -> str:
    return f"{x:,.{nd}f}"

# ----------------------------------------------------------------------------
# Shorthand for values used in the text
# ----------------------------------------------------------------------------
A, T, F, LG, AV, L = S["audit"], S["token"], S["fairness"], S["ledger"], S["availability"], S["lab"]
NP = A["prompts"]
CH = A["cheats"]
MODEL_SHORT = A["model"].split("/")[1]
BIG = LG["batches"][-1]
R2048, R4096 = T["blind_rsa"]


def cell(load, pol, key, stat="median"):
    return F["table"][f"{load}|{pol}"][key][stat]


def sections_1_to_5():
    # ------------------------------------------------------------------ 1
    h2("1", "Introduction", "intro")
    p("Running a capable language model costs either a large computer or a metered cloud account. Most households and small teams "
      "have neither, yet between them they own a great deal of idle memory and compute. MeshStack&trade; already lets one owner pool "
      "their own devices: the previous THOX report specified pipeline sharding, a keyed KV graph and lease-fenced device roles for a "
      "single household [@thoxP1], and Auto Device Role Mode lets an owner's device lend itself to that owner's mesh under a lease "
      "[@thoxRole]. This paper takes the next step and asks what has to be true before <i>different</i> owners can pool hardware: "
      "a member adds a device to a community pool, and any MeshStack subscriber can run inference on that pool, or reach a hosted "
      "cloud model through it, without the pool learning who they are.")
    p("Crossing the ownership boundary changes the problem. Inside one household every device answers to the same person. In a "
      "community pool the device that executes a stage belongs to a stranger, the requester is a stranger to that device, and neither "
      "has a reason to trust the other. Volunteer computing met the same boundary two decades ago and answered with redundancy and "
      "spot checks [@boinc; @sarmenta]. Petals showed that a large language model can be served by volunteers holding layer ranges "
      "[@petals; @petalsinternet]. What neither settles for a consumer product is the combination THOX needs: the owner of a "
      "contributed device stays sovereign, the requester stays unidentifiable, cheating is caught and costs more than it earns, "
      "contribution earns access without a currency, and none of the bookkeeping slows a token.")
    p("We are direct about one limit from the first page. A device that computes on a request can read what it computes. Recent work "
      "reconstructs prompts from the intermediate activations that pipeline stages exchange [@pia], and the THOX security model "
      "already records the same fact for KV state [@thoxSec]. The community plane in this paper therefore offers <i>identity</i> "
      "privacy, not <i>content</i> privacy against the executing contributor. Requests that need content privacy stay on the "
      "requester's own devices, and the system refuses to route them anywhere else.")
    p("Contributions:")
    ol([
        "<b>A design for a member-contributed pool on MeshStack</b> with four planes (local, own mesh, community, cloud), ten numbered "
        "requirements, and each requirement mapped to a test that ran (Sections 3 to 5).",
        "<b>Requester unlinkability carried by blind-signed tokens</b> (RFC 9474) and sealed envelopes through a relay (RFC 9180), "
        "with priority carried by the token's issuing key so that contribution can raise priority without identifying the requester "
        "(Section 4.2).",
        f"<b>A measured comparison of two audit predicates on a real model.</b> Re-executing a request and comparing output tokens, "
        f"the gate MeshStack already uses to certify stage decomposition, misses a contributor running fp16 weights on "
        f"{NP - CH['fp16w']['token_detect_prompts']} of {NP} prompts. Comparing a SHA-256 digest of the stage boundary catches every "
        f"cheat class we tried on every prompt (Section 6.2).",
        "<b>A settlement ledger that behaves like a blockchain where it matters and costs nothing where it does not</b>: signed "
        "receipts in band, Merkle batching and witness cosigning after the request, measured (Sections 4.5 and 6.5).",
        f"<b>A working virtual lab</b>: {L['processes']} operating-system processes with real cryptography and a real model, "
        f"{len(L['summary'])} scenarios, one evidence file. Every lab claim in this paper is a field of that file (Section 6.6).",
        "<b>Consolidation with the companion work</b> [@thoxCC]: its plan-wide admission rule, execution contexts and "
        "replica-first default are adopted (Section 4); its lab is reproduced on a second host and its decode-cycle model is "
        "re-derived and applied to this design (Sections 6.7 and 6.8).",
    ])

    # ------------------------------------------------------------------ 2
    h2("2", "Background and related work", "related")
    h3("2.1 Pooled inference across owners")
    p("Petals serves large models by letting volunteers host contiguous transformer blocks and chaining them per request, with "
      "fault-tolerant routing when a server disconnects [@petals; @petalsinternet]. Parallax schedules layer placement and "
      "request-time pipeline selection over a decentralised pool of heterogeneous GPUs [@parallax]. Prima.cpp targets home clusters "
      "of mixed, low-resource devices [@primacpp]. These systems establish that the pipeline form works over consumer links; they "
      "are the base this paper builds on, not a contribution of it. None of them hides the requester from the pool, and none binds "
      "admission to a subscription.")
    h3("2.2 Verifying work done by strangers")
    p("Volunteer computing verifies results by replication and spot checks; Sarmenta's analysis of spot-checking with blacklisting "
      "and credibility is the classical treatment [@sarmenta], and BOINC ships replication-based validation [@boinc]. For model "
      "inference, optimistic schemes re-execute on dispute [@opml], Proof of Sampling derives an equilibrium in which sampled "
      "verification makes honesty the rational strategy [@pos], Proof of Quality replaces exact verification with quality "
      "consensus [@poq], SVIP trains a proxy task on returned hidden states to detect model substitution [@svip], and TOPLOC "
      "commits to intermediate activations with a locality-sensitive hash that tolerates hardware differences [@toploc]. Our audit "
      "is the simplest member of this family: an exact digest of the stage boundary, replayed by an auditor in the same "
      "determinism class. Its only novelty is the measurement in Section 6.2 that the weaker, more natural predicate "
      "(compare the tokens) does not work, and the binding of the audit to signed receipts and a public ledger.")
    h3("2.3 Asking without being identified")
    p("Privacy Pass separates the party that attests a client from the party that serves it, using tokens the issuer cannot link to "
      "their redemption [@rfc9576; @rfc9578]; the publicly verifiable variant uses RSA blind signatures [@rfc9474]. Oblivious HTTP "
      "places a relay between client and gateway so that the relay sees the client's address but not the request and the gateway "
      "sees the request but not the address [@rfc9458], building on HPKE [@rfc9180]. Apple's Private Cloud Compute combines both, "
      "an OHTTP relay and RSA blind-signature credentials, in front of attested servers [@pcc]. Onion routing generalises the relay "
      "to multiple hops [@tor]. We adopt the Privacy Pass and OHTTP split unchanged and apply it to a pool whose servers are other "
      "members' devices.")
    h3("2.4 What a stage can learn")
    p("Embedding inversion recovers text from dense embeddings [@vec2text] and from next-token distributions [@lmi]. For the "
      "pipeline setting specifically, prompt inversion against collaborative LLM inference reconstructs inputs from intermediate "
      "activations [@pia], and proposed defences trade utility for reduced leakage without eliminating it [@piadef]. Cryptographic "
      "private inference remains orders of magnitude slower than plaintext [@puma]. Trusted execution environments bound the "
      "exposure with a modest overhead on server CPUs [@teecost] and are the long-term answer the THOX security model already "
      "names [@thoxSec]; contributed consumer devices do not offer one today.")
    h3("2.5 Sharing fairly")
    p("The Virtual Token Counter serves the least-served client first and lifts a returning client's counter so idle time banks no "
      "credit [@vtc]; later work adds prefix locality [@dlpm] and per-token latency isolation [@fairinference]. Dominant Resource "
      "Fairness is the multi-resource baseline [@drf]. All of these keep a counter per client. Section 4.4 explains why an "
      "unlinkable pool cannot, and what replaces it.")
    table(["System", "Hardware from", "Requester hidden from pool", "Result verification", "Access model", "Owner pre-emption"], [
        ["Petals [@petals; @petalsinternet]", "volunteers", "no", "none stated in the abstracts we cite", "open", "server may leave"],
        ["Parallax [@parallax]", "decentralised GPU pool", "no", "not in scope", "open pool", "dynamic availability"],
        ["BOINC [@boinc]", "volunteers", "n/a (project is requester)", "replication", "project-run", "volunteer preferences"],
        ["Proof of Sampling [@pos]", "staked nodes", "no", "sampled re-execution, game-theoretic", "payment", "n/a"],
        ["Private Cloud Compute [@pcc]", "one operator", "yes (relay and blind tokens)", "attested software", "device entitlement", "n/a"],
        ["<b>This paper</b>", "subscribers' own devices", "yes (relay and blind tokens)", "boundary-digest audit, signed receipts, public ledger", "subscription, non-transferable credits", "owner always wins within one chunk"],
    ], caption="Table 1. Positioning. Entries for other systems restate their own published descriptions; they are not measurements by THOX.")

    # ------------------------------------------------------------------ 3
    h2("3", "System and threat model", "model")
    h3("3.1 Parties")
    ul([
        "<b>Member.</b> A MeshStack subscriber. A member may be a <i>requester</i>, a <i>contributor</i> (owner of one or more enrolled devices), or both.",
        "<b>Subscription authority.</b> Knows accounts. Issues device certificates and blind-signed tokens. Holds the credit balance that sets issuance budgets.",
        "<b>Coordinator.</b> Keeps pool membership, redeems tokens, issues leases, accepts fraud proofs. Never learns an account.",
        "<b>Relay.</b> Forwards sealed envelopes. Holds no decryption key.",
        "<b>Stage node.</b> A contributed device holding a contiguous layer range of one certified model.",
        "<b>Auditor.</b> A node in the same determinism class as the stage it checks. It replays sampled hops.",
        "<b>Cloud gateway.</b> A hosted model provider reached through the relay. It can read the prompt; it cannot tell whose it is.",
        "<b>Ledger and witnesses.</b> An append-only log of credits and penalties, and independent parties that cosign its heads.",
    ])
    h3("3.2 Adversaries")
    p("<b>Curious contributor:</b> follows the protocol and tries to learn who is asking and what. <b>Lazy or dishonest contributor:</b> "
      "returns cheaper or wrong results to earn credit (skips layers, substitutes lower precision, perturbs outputs). <b>Free rider:</b> "
      "a subscriber, or a non-subscriber, who tries to consume more than their share. <b>Curious operator:</b> the coordinator or the "
      "authority tries to link requests to accounts, or rewrites the credit history. <b>Network observer:</b> sees traffic between "
      "parties. Out of scope: a contributor reading the activations it legitimately computes (Section 1), collusion between the "
      "relay and the coordinator, traffic-timing correlation, and physical attacks on devices.")
    h3("3.3 Requirements")
    table(["", "Requirement"], [
        ["R1", "<b>Owner sovereignty.</b> Contribution is opt-in per device and per exact model identifier. An owner who returns to their device waits at most one service chunk; community work never evicts owner work."],
        ["R2", "<b>Requester unlinkability.</b> No party other than the subscription authority learns which member made a request, and the authority cannot link a token it issued to the request that redeems it."],
        ["R3", "<b>Stated content exposure.</b> Every request carries a privacy class. <code>local_only</code> never leaves the device; <code>mesh_only</code> never leaves the owner's devices; <code>community</code> accepts that the executing contributor can read activations; <code>cloud</code> accepts that the provider can read the prompt; <code>confidential</code> requires an attested execution boundary on every stage that handles plaintext, which no contributed consumer device offers today, so it is refused. A request is refused, not downgraded, when its class forbids a plane."],
        ["R4", "<b>Subscriber-only, bounded admission.</b> Only tokens issued to subscribers are accepted. Each token authorises one bounded service quantum and is spent once. Issuance per account per epoch is bounded."],
        ["R5", "<b>Auditable integrity.</b> Every hop yields a signed receipt binding input and output digests. A contributor that returns a wrong result is caught with probability approaching one under sampled audit, and loses more than it gained."],
        ["R6", "<b>Contribution earns access without identifying the requester.</b>"],
        ["R7", "<b>Plane provenance.</b> Every response is labelled with the plane that produced it. A cloud-hosted model is never advertised as contributed compute [@thoxADR]."],
        ["R8", "<b>No cross-member cache.</b> KV state stays keyed to and readable by one principal, as decisions D19 and D43 require [@thoxDec]."],
        ["R9", "<b>Verifiable settlement off the token path.</b> Credits and penalties are append-only, publicly checkable and replayable, carry no requester identity, and add no work between two generated tokens."],
        ["R10", "<b>Fail closed with attribution.</b> A failed hop, an audit mismatch, a broken receipt chain or a stale lease stops that path and names the hop. Recovery is a new route, never a silent degradation."],
    ], caption="Table 2. Requirements. Section 5 maps each to the test that exercised it.")

    # ------------------------------------------------------------------ 4
    h2("4", "Design", "design")
    h3("4.1 Planes and seat order")
    OUT.append("""
<div class="arch">
  <div class="arch-row"><div class="box ghost"><b>Requester's device (local plane)</b><span>prompt, tokenizer, embeddings, first layer range and output head stay here; token wallet; sealed transport; receipt checks</span></div></div>
  <div class="arch-arrow">sealed envelopes only (HPKE), always through the relay</div>
  <div class="arch-row three">
    <div class="box"><b>Subscription authority</b><span>accounts, device certificates, blind token issuance with budgets, credit balance. Sees who; never sees a token or a request.</span></div>
    <div class="box hi"><b>Relay</b><span>forwards ciphertext, holds no key. Sees that someone asked; never sees who is authorised or what was asked.</span></div>
    <div class="box"><b>Coordinator</b><span>pool membership from signed advertisements, token redemption, leases, tier-weighted admission, fraud proofs. Sees a valid token; never sees an account.</span></div>
  </div>
  <div class="arch-arrow">lease (signed route, TTL, quantum) &rarr; hops carry activations, receipts come back</div>
  <div class="arch-row four">
    <div class="box"><b>Stage node (community plane)</b><span>contributed device, layer range, owner switch, Ed25519 receipts</span></div>
    <div class="box"><b>Stage node</b><span>direct stage-to-stage forwarding; last stage returns one position</span></div>
    <div class="box"><b>Auditor</b><span>same determinism class; replays sampled hops; signs findings</span></div>
    <div class="box ghost"><b>Cloud gateway (cloud plane)</b><span>hosted model; reads the prompt, not the account; labelled</span></div>
  </div>
  <div class="arch-arrow">after the request: receipts &rarr; credits and penalties</div>
  <div class="arch-row two">
    <div class="box"><b>Settlement ledger</b><span>hash-chained Merkle epochs of coordinator-signed records; inclusion proofs; replayable balances</span></div>
    <div class="box dim"><b>Witnesses</b><span>cosign a head only if it extends the one history they have seen</span></div>
  </div>
</div>
<figcaption><b>Figure 1.</b> Parties and what each can see. Shaded boxes are not operated by members. The own-mesh plane of the previous report sits between local and community and is unchanged.</figcaption>
""")
    p("A request tries planes in a fixed order and stops at the first that both fits the model and is permitted by the privacy class: "
      "the local model, the owner's own mesh [@thoxP1; @thoxRole], the community pool, then the cloud plane. This extends the seat "
      "order of Auto Device Role Mode by one seat and keeps its rule that an empty pool is a fall-through, not an error. The plane "
      "that served a response is part of the response.")
    p("The privacy classes of R3 correspond to the execution contexts of the companion paper [@thoxCC], which we adopt: "
      "owner-controlled mesh (<code>local_only</code>, <code>mesh_only</code>), trusted community hosts (<code>community</code>), "
      "attested confidential hosts (<code>confidential</code>) and external model service (<code>cloud</code>). They are policy "
      "contexts, not a ranking. We also adopt its plan-wide admission rule. A job " + ieq("j") + " may run on a plan " + ieq(r"\pi") +
      " at time " + ieq("t") + " only if")
    eq(r"\begin{aligned}\mathrm{Eligible}(j,\pi,t) ={}& E_j(t)\;\wedge\;C_j(\pi,t)\;\wedge\;R_j(\pi)\\ &\wedge\bigwedge_{v\in V(\pi)} A(j,v,t)\;\wedge\bigwedge_{e\in F(\pi)} D(j,e,t)\end{aligned}")
    p("where " + ieq("E") + " is subscriber entitlement (here, a valid unspent token), " + ieq("C") + " consent (the privacy class), " +
      ieq("R") + " model rights and compatibility (the certified fingerprint), " + ieq("A") + " admission at every stage (enrolled, "
      "owner idle, not suspended, lease valid) and " + ieq("D") + " authorisation of every data edge (sealed to the next hop's key). "
      "Only eligible plans are ranked; an ineligible candidate is excluded, never given a worse price. In the lab the signed lease "
      "is the plan: it carries a plan digest over route, keys, model fingerprint, quantum and expiry, and every receipt repeats "
      "that digest.")
    p("<b>Replica first.</b> Also following [@thoxCC], the default route is a whole replica: if one eligible device can hold all "
      "of the remote layers, use it, and split across devices only when no single device can and a measured benefit exists. A "
      "replica route has fewer hops, exposes activations to one contributor instead of two, and needs one receipt per token. "
      "Section 6.7 measures the difference in the lab and calculates it for wide-area links.")
    h3("4.2 Tokens: authorised, bounded, unlinkable")
    p("The authority holds one RSA key per <i>tier</i>. To obtain a token the member's device draws a random 32-byte nonce, appends "
      "the intended audience (<code>community</code> or <code>cloud</code>), blinds the encoded message under the tier's public key and "
      "sends the blinded value with its account credential. The authority checks the account and the tier budget, signs the blinded "
      "value, and returns it. The device removes the blinding factor and holds a standard RSASSA-PSS signature on a message the "
      "authority has never seen.")
    eq(r"\begin{aligned} z &= \mathrm{EMSA\text{-}PSS}(m)\cdot r^{e} \bmod n, &\qquad \hat{s} &= z^{d} \bmod n,\\ s &= \hat{s}\cdot r^{-1} \bmod n, &\qquad s^{e} &\equiv \mathrm{EMSA\text{-}PSS}(m) \pmod n \end{aligned}")
    p("The redeemer (coordinator or cloud gateway) verifies " + ieq("s") + " under the tier key, checks the audience, and records "
      + ieq(r"\mathrm{SHA\text{-}256}(m)") + " in a spent set. One token buys one request of at most " + ieq("Q") +
      " generated tokens. The tier is visible to the redeemer because it is the key that verifies; nothing else about the holder is.")
    callout("Proposition 1 (unlinkability, inherited)",
            "For a fixed public key and any two messages, the blinded values the authority sees are identically distributed, because "
            + ieq("r") + " is uniform over the units modulo " + ieq("n") + " and so is " + ieq(r"r^{e}") + ". The authority's view at "
            "issuance is therefore independent of the token later redeemed. This is the blindness property of RFC 9474 [@rfc9474]; "
            "we rely on it and do not re-prove it. The anonymity set of a redeemed token is every member issued a token of that tier "
            "in that key epoch, so tiers must stay few and keys must rotate on a schedule, not per member.")
    h3("4.3 The request path")
    algo("Algorithm 1. One request on the community plane", [
        "1  device: token <- wallet(tier, aud=community)            # issued earlier, unlinkable",
        "2  device -> relay -> coordinator: seal(lease request, token, privacy class)",
        "3  coordinator: verify token, check spent set, refuse local_only / mesh_only,",
        "               pick one eligible node per remote stage (not owner-active, not suspended, not busy),",
        "               return signed lease {route, TTL, quantum Q}",
        "4  for step t = 0 .. Q-1:",
        "5     device: h0 <- local layers(embed(prompt + generated))",
        "6     device -> relay -> stage 1: seal(lease, t, h0)         # stage checks lease signature, route, owner switch",
        "7     stage 1: h1 <- layers(h0); receipt1 = sign(lease, t, SHA256(h0), SHA256(h1))",
        "8     stage 1 -> stage 2 directly: seal(lease, t, h1, receipt1)",
        "9     stage 2: h2 <- layers(h1)[last position]; receipt2 = sign(lease, t, SHA256(h1), SHA256(h2))",
        "10    reply to device, sealed to its one-time key: h2, receipt1, receipt2",
        "11    device: verify both signatures and the chain  in1 = SHA256(h0), in2 = out1, out2 = SHA256(h2)",
        "12    device: with probability q send (h0, receipts) to an auditor; on mismatch submit fraud proof, reroute, restart",
        "13    device: next token <- argmax(head(h2))                 # head stays local",
        "14 device -> coordinator: close(lease, receipts)             # credits go to the ledger after the fact",
        "   any failure at 6-11: reroute excluding the named hop and repeat step t (hops are stateless in the lab)",
    ])
    p("Three properties of this path matter. Token identifiers never leave the device: embeddings and the output head are local, so "
      "contributors receive activations only. The receipt chain lets the device detect, without any replay, a stage that signs one "
      "output and forwards another, because the next stage signs what it actually received. And the owner switch is checked on every "
      "hop, so a returning owner is served at the next hop boundary (R1).")
    h3("4.4 Admission when the pool cannot count per member")
    p("Fair serving normally keeps a service counter per client [@vtc]. A pool that cannot link two requests from the same member "
      "cannot. We move the per-member accounting to the one party that knows members, the authority, and express it as an issuance "
      "budget: each account may draw a bounded number of tokens per epoch. Contribution raises the budget and unlocks a higher tier. "
      "The coordinator then needs only per-tier state. It grants the queued tier with the least service per unit weight, with the "
      "counter lift of VTC applied per tier so an idle tier banks nothing.")
    eq(r"\begin{aligned}\text{grant tier } \tau^{*} &= \arg\min_{\tau \in \text{queued}} \frac{\sigma_{\tau}}{w_{\tau}},\qquad \sigma_{\tau} \leftarrow \sigma_{\tau} + Q \text{ on grant},\\ B_{m} &= B_{0} + \left\lfloor \beta\, c_{m} \right\rfloor \end{aligned}")
    p("Here " + ieq(r"\sigma_\tau") + " is service granted to tier " + ieq(r"\tau") + ", " + ieq(r"w_\tau") + " its weight, " + ieq("B_m") +
      " member " + ieq("m") + "'s budget and " + ieq("c_m") + " the verified service that member's devices gave to others. Credits are "
      "non-transferable and buy only tokens. Decision D20 rejected a payments market for MeshStack [@thoxDec]; this design stays inside "
      "that decision. The cost of moving fairness to issuance is that a budget is not work-conserving: capacity can sit idle while a "
      "member waits for their bucket to refill. Section 6.4 measures that cost in simulation. The remedy is to index issuance to "
      "pool load: the coordinator publishes one aggregate bit (a route is free and nothing is queued), and while it is set the "
      "authority issues one base-tier token past the budget. The bit identifies nobody. Contributor-tier tokens are never issued as "
      "surplus.")
    h3("4.5 Audits, penalties and the settlement ledger")
    p("An audit replays a hop. The device sends the auditor the stage input it produced and the receipts it received. The auditor, "
      "holding the same layer ranges at the same engine build, recomputes each remote stage in turn and compares the SHA-256 digest "
      "of its output with the digest the contributor signed. A mismatch yields a <i>fraud proof</i>: the contributor's signed receipt "
      "and the auditor's signed finding over the same input digest with a different output digest. The coordinator verifies both "
      "signatures and suspends the node; the authority zeroes the owner's credit; the device reroutes and restarts the request so "
      "that nothing the cheater touched is kept.")
    callout("Proposition 2 (detection)",
            "Let a contributor cheat on every request, let each request be audited independently with probability " + ieq("q") +
            ", and let an audit expose the cheat with probability " + ieq("d") + ". The probability it is caught within " + ieq("n") +
            " requests is " + ieq(r"1-(1-qd)^{n}") + " and the expected number of requests before detection is " + ieq(r"1/(qd)") +
            ". <i>Proof.</i> Audits are independent Bernoulli trials with success probability " + ieq("qd") + "; the waiting time is geometric.")
    callout("Proposition 3 (deterrence)",
            "Let " + ieq("g") + " be the credit a contributor gains per cheated request and " + ieq("L") + " what it loses on detection "
            "(forfeited balance and the value of suspension). Cheating has negative expected value when " + ieq(r"q\,d\,L > (1-qd)\,g") +
            ", that is when " + ieq(r"q > \dfrac{g}{d\,(L+g)}") + ". <i>Proof sketch.</i> Per request the cheater gains " + ieq("g") +
            " with probability " + ieq("1-qd") + " and loses " + ieq("L") + " with probability " + ieq("qd") + ". The bound is only as "
            "good as " + ieq("d") + ": an audit predicate that rarely exposes a cheat makes every audit rate insufficient, which is "
            "why Section 6.2 measures " + ieq("d") + " per cheat class.")
    p("Settlement is where a blockchain-like structure earns its place, and where it must not cost latency. Receipts are signed in "
      "band because audits need them anyway. Everything else happens after the request. The coordinator signs a record per lease "
      "(member credited, token-steps served) or per penalty and appends it to a log. Each epoch the log is rolled into a Merkle tree "
      "with the hashing of Certificate Transparency [@rfc9162]; the tree head names its epoch, size, root and the hash of the "
      "previous head; " + ieq("W") + " witnesses cosign it. A member proves a credit, or anyone proves a penalty, with an inclusion "
      "proof of " + ieq(r"\lceil \log_2 N \rceil") + " hashes. Balances are a deterministic replay of the log, so the authority's "
      "balance can be checked by anyone holding it.")
    callout("Proposition 4 (no quiet rewrite)",
            "A witness cosigns a head only if its epoch is the next one the witness expects and its <code>prev</code> field equals the "
            "hash of the last head that witness cosigned. A head is accepted with more than " + ieq("W/2") + " cosignatures. Then two "
            "different heads for the same epoch cannot both be accepted unless some witness cosigned both, which an honest witness "
            "never does. <i>Proof.</i> Two majorities of " + ieq("W") + " witnesses intersect; the common witness signed at most one "
            "head for that epoch. The log operator can stop publishing; it cannot show two members two histories.")
    p("We chose a witnessed transparency log over a consensus chain on purpose. A public chain or a per-hop BFT round would put "
      "seconds or a consensus round between tokens. A permissioned BFT committee that orders only epoch heads is a compatible later "
      "step if THOX should not be the sole log operator; it changes who signs heads, not the request path.")
    h3("4.6 The cloud plane")
    p("Subscribers also want models no pool of small devices can hold. The cloud plane reaches a hosted model through the same relay "
      "with the same tokens, bound to the <code>cloud</code> audience so a community token cannot be replayed there. The gateway can "
      "read the prompt; that is what hosted inference is. What the plane adds is that the provider receives a request it can "
      "authorise and bill against THOX without learning which subscriber sent it, in the manner of [@rfc9458; @pcc]. The response "
      "carries the label <code>cloud</code>, and the coordinator refuses any advertisement that lists a cloud-tagged model as "
      "contributed compute, which is ADR-025 enforced at the pool boundary [@thoxADR].")
    h3("4.7 Availability")
    p("A route needs one online, owner-idle contributor per remote stage. If each of " + ieq("n_s") + " enrolled devices for a stage is "
      "independently available with probability " + ieq("a") + ", a route with " + ieq("r") + "-fold choice per stage across " + ieq("S") +
      " remote stages exists with probability")
    eq(r"P_{\text{route}} = \left[\sum_{k=r}^{n_s}\binom{n_s}{k} a^{k}(1-a)^{n_s-k}\right]^{S}")
    rows = [[f"{r_['availability']:.2f}", str(r_["enrolled_per_stage_r1"]), str(r_["enrolled_per_stage_r2"])] for r_ in AV["rows"]]
    table(["Device availability a", "Devices per stage for one candidate (r = 1)", "Devices per stage for a spare (r = 2)"], rows,
          caption=f"Table 3. Calculated. Smallest enrolment per stage for a route to exist with probability at least {AV['target']} "
                  f"across {AV['remote_stages']} remote stages. Independence is an assumption; household devices sleep at the same hours.")

    # ------------------------------------------------------------------ 5
    h2("5", "Implementation", "impl")
    p(f"The virtual lab is {L['processes']} operating-system processes on one host that speak HTTP over loopback: authority, "
      "coordinator, relay, four contributor stage nodes, one auditor, a cloud gateway, the settlement ledger, three witnesses, and "
      f"the requester's device. The model is {MODEL_SHORT} [@smollm] ({A['params_m']:.0f}M parameters, {A['layers']} layers) at a "
      "pinned revision, split into three ten-layer stages. Each stage node loads the checkpoint and keeps only its own layer range "
      f"({L['A']['nodes']['B1']['params_held'] / 1e6:.1f}M of {L['A']['nodes']['B1']['params_total'] / 1e6:.1f}M parameters). "
      "Cryptography is real: RSA blind signatures are implemented from RFC 9474 in Python integers and checked against the RFC's "
      "Appendix A.3 vector and against an independent library verifier; HPKE [@rfc9180], Ed25519 [@rfc8032] and RSASSA-PSS "
      "verification come from the <code>cryptography</code> library. Hops are stateless in the lab (each step recomputes the "
      "sequence), which makes reroute trivial and costs throughput we do not report.")
    p("The lab is virtual in one sense only: every party is a process, not a machine. It establishes that the protocol composes, "
      "that the refusals refuse, and that the information each party receives is what the design says. It establishes nothing about "
      "THOX devices, wide-area links or throughput.")
    table(["Req.", "Exercised by", "Result recorded"], [
        ["R1", "Lab D (owner returns mid-request); simulation owner-delay bound", f"request moved off the owner's device at the next hop, output token-exact: {L['D']['token_exact']}; simulated worst owner wait {F['owner_delay_max_s']:.1f} s against a one-chunk bound of {F['worst_chunk_s']:.1f} s"],
        ["R2", "Lab B (tokens), Lab I (wire scan)", f"authority saw the account and no token value; coordinator, relay, stage nodes and gateway received no account on the wire ({L['I']['tokens_issued']} tokens issued)"],
        ["R3", "Lab B, Lab H", f"<code>local_only</code> at the coordinator: {L['B']['local_only_class']}; <code>mesh_only</code>: {L['B']['mesh_only_class']}; <code>confidential</code>: {L['B']['confidential_class']}; <code>community</code> class at the cloud gateway: {L['H']['community_class_at_cloud']}"],
        ["R4", "Lab A, Lab B, Lab G", f"non-subscriber: {L['B']['issue_non_subscriber']['error']}; second redemption: {L['B']['redeem_again']}; forged signature: {L['B']['forged_signature']}; over budget: {L['B']['issue_over_budget']['error']}"],
        ["R5", "Experiment E1; Lab C, Lab F", f"digest audit exposed {sum(c['digest_detect_prompts'] for c in CH.values())} of {NP * len(CH)} cheated requests; lab fraud proof accepted, node suspended"],
        ["R4, R6", "Lab L", f"past the budget with the pool idle: issued as surplus ({L['Lx']['over_budget_while_idle']['code']}); with every route leased: {L['Lx']['over_budget_while_busy']['error']}; contributor tier as surplus: refused ({L['Lx']['contributor_tier_never_issued_as_surplus_code']})"],
        ["R6", "Lab G", f"contributor's contributor-tier budget {L['G']['contributor_contrib_budget']}, consumer's {L['G']['consumer_contrib_budget']}; grant order " + " ".join(t[0] for t in L['G']['grant_order'])],
        ["R7", "Lab A, Lab H", f"cloud-tagged advertisement: {L['A']['cloud_model_tag_advert']['error']}; cloud response label: {L['H']['plane_label']}"],
        ["R8", "By construction", "stateless hops; no KV state leaves a process in the lab. Not a test of the production KV graph."],
        ["R9", "Experiment E4; Lab J", f"{L['J']['entries']} records, {L['J']['witness_cosignatures_valid']} of {L['J']['witnesses']} cosignatures valid, replayed balances equal the authority's: {L['J']['replay_matches_authority']}, forged head cosigned by {L['J']['fork_attempt']['cosigned_by']} witnesses"],
        ["R10", "Lab D, Lab E, Lab F", f"killed contributor named in the error ({L['E']['killed']}), rerouted, output token-exact: {L['E']['token_exact']}"],
    ], caption="Table 4. Requirement to test. Lab letters refer to Section 6.6. Every cell in the right column is read from the evidence file.")


def sections_7_to_end():
    # ------------------------------------------------------------------ 7
    h2("7", "Discussion and limitations", "limits")
    ul([
        "<b>Content is not private from the executing contributor.</b> A stage node receives activations, and published attacks invert activations to text [@pia]. The lab's wire scan shows what crosses the wire unsealed, not what a recipient can decrypt and compute on. The community plane is for requests whose owner accepts that exposure; the default class for anything personal should remain <code>local_only</code>, as the security model's operator checklist already says [@thoxSec].",
        "<b>The digest audit is bound to a determinism class.</b> Digests matched across repeats, across one and two threads, and across separate processes on this host. They were not tested across CPU models, accelerators, operating systems or engine builds, where bit-identical floating point is not expected. Decision D31 already limits bit-exact promises to a pinned engine, hardware class and batch shape [@thoxDec]. Until a tolerant commitment such as TOPLOC [@toploc] is evaluated, an auditor must be in the contributor's class, which constrains who can audit whom.",
        f"<b>Host, model and scale.</b> One 2-vCPU x86_64 container; {MODEL_SHORT} at {A['params_m']:.0f}M parameters; {NP} prompts of {A['new_tokens']} greedy tokens; {A['reps']} timing passes for the staging overhead; {R2048['runs']} repetitions for cryptographic timings ({R4096['runs']} at RSA-4096, {BIG['reps']} for the largest Merkle batch). Detection rates over {NP} prompts are coarse: zero of {NP} does not mean zero.",
        "<b>The lab is one host.</b> No THOX device, no second machine, no wide-area link, no WireGuard tunnel, no real relay operator. Hops are stateless and recompute the sequence at every step, so lab latency says nothing about a KV-cached engine. No throughput or latency figure in this paper is a product claim; decision D37 forbids them until the benchmark gate passes [@thoxDec].",
        "<b>Admission results are a simulation</b> with abstract service rates, exponential owner activity and independent members. Real households are correlated: devices sleep at night together. The budget policy's parameters were chosen once and not tuned.",
        "<b>Collusion and traffic analysis are out of scope.</b> A relay that colludes with the coordinator links address to request; this is the standard OHTTP assumption [@rfc9458] and requires the two to be operated by different parties. Request timing and size are visible to the relay. With few members online, the anonymity set is small regardless of cryptography.",
        "<b>Sybil resistance is economic.</b> A subscription is the cost of an identity; per-account budgets and device limits bound what one identity can draw. A wealthy adversary can buy many subscriptions. Auditors are assumed honest; a dishonest auditor could frame a contributor, which is why a fraud proof should be re-checkable by a second auditor before a permanent penalty. The lab accepts a single finding.",
        "<b>Advertised capacity is self-reported.</b> A device can overstate what it holds. The lab certifies only the model fingerprint string; binding a layer package to a measured hash at enrolment is the production requirement (decisions D16 and D17).",
        "<b>Topology timing.</b> The replica-against-pipeline comparison is 30 trials per arm on one host over loopback. Its low dispersion is a property of this host on this day; the companion lab showed the opposite on its authors' host. The network figures in Table 8 are calculated from assumptions.",
        "<b>Two labs, not one.</b> The companion lab and this lab share no code and answer different questions. A pass in one says nothing about the other. Their consolidation into the canonical MeshStack lines is future work.",
        "<b>Not built.</b> Device attestation, key rotation and token epochs, the production coordinator and Supabase store, KV-cached stages with migration, the own-mesh plane inside this lab, a second auditor, a BFT committee for heads, billing for the cloud plane, and every client surface.",
        "<b>Three prior decisions bear on this design and are the founders' to keep or change:</b> D20 (no payments market: we use non-transferable credits), D43 (no cross-principal cache until a security review: we share none), and ADR-025 (cloud tags are never mesh compute: we enforce it and add a separate, labelled cloud plane).",
        "<b>Not peer reviewed.</b> This is a preprint prepared by THOX.ai Research with AI assistance (Appendix C).",
    ])

    # ------------------------------------------------------------------ 8
    h2("8", "Conclusion", "concl")
    p("A community pool for inference needs five things at once: owners who never lose their own device, requesters the pool cannot "
      "identify, cheats that are caught and cost more than they earn, access that follows contribution without a currency, and "
      "bookkeeping that does not sit between tokens. Each has a known building block. This paper assembles them on MeshStack, runs "
      "the assembly end to end in a virtual lab, and reports the one result that changed the design: the natural audit, comparing "
      f"output tokens, let an fp16 substitution through on every one of {NP} prompts, while a digest of the stage boundary caught "
      "everything. It also states plainly what the pool does not give: content privacy from the device that does the work. With that "
      "limit on the label, pooled hardware plus an anonymous path to hosted models is a credible way to give subscribers inference "
      "they could not otherwise afford.")

    # ------------------------------------------------------------------ 9
    h2("9", "Roadmap", "roadmap")
    p("Ordered by what unblocks what.")
    ol([
        "<b>Decide D20, D43 and ADR-025 for the community scope, the requester-identity default (pseudonym or blind token) and one author roster.</b> The design assumes the three decisions stand.",
        "<b>One lab.</b> Bring the companion lab's mutual TLS, per-call grants, tenant namespaces and transactional outbox together with this lab's tokens, audits and witnessed ledger on the canonical lines; fix the certificate identifiers.",
        "<b>Two-machine lab.</b> Run the same roles on two fleet hosts over a WireGuard tunnel, with the relay on a third party's host. Exit evidence: the same evidence file with real addresses in the wire scan.",
        "<b>Determinism classes.</b> Measure boundary-digest equality across the device classes that will contribute; where it fails, evaluate a tolerant commitment and report its false-accept rate against the six cheat classes.",
        "<b>KV-cached stages.</b> Replace stateless hops with the stage-server engine and its token-log replay; re-run scenarios D, E and F.",
        "<b>Carry the pool into the canonical lines.</b> Extend the Auto Device Role Mode tables with a community scope, add tier keys to the authority, and land the ledger beside the coordinator in ttracx/sadie-mesh.",
        "<b>Second auditor and appeal.</b> Require two independent findings before a permanent penalty.",
        "<b>Device benchmark under the claims register.</b> Thirty runs per configuration on THOX devices before any performance sentence is written.",
        "<b>External review</b> of the token, relay and ledger construction before any public release.",
    ])

    # ------------------------------------------------------------------ A
    h2("A", "Appendix A. Reproducibility", "appA")
    p(f"Environment: Linux container, x86_64, 2 vCPU, 7 GB RAM; Python {A['host']['python']}; PyTorch {A['host']['torch']} (CPU wheel); "
      "transformers 5.22.2; cryptography 50.0.1; NumPy; Matplotlib. Node 22 with katex 0.16.11, @fontsource/inter 5.1.0, "
      "@fontsource/jetbrains-mono 5.1.1 and Playwright for rendering. Greedy decoding throughout; the model revision is pinned.")
    algo("Commands (from the artifact root)", [
        "pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install transformers safetensors cryptography numpy matplotlib pypdf pillow",
        "python3 exp/audit_experiments.py         # downloads the model; about 10 minutes on 2 vCPU",
        "(cd exp && python3 audit_timing.py)      # five alternating timing passes",
        "python3 exp/token_experiments.py         # RFC 9474 known-answer test, blind RSA and HPKE timings",
        "python3 exp/fairness_sim.py              # 30 seeds x 5 loads x 4 policies",
        "python3 exp/ledger_experiments.py",
        "python3 -m lab.run_lab                   # the virtual lab; writes lab/evidence/evidence.json; exit code 0 only if every scenario passes",
        "# companion lab (needs Python 3.12): unzip companion/THOX_MeshStack_Virtual_Lab_v1.0.zip; pip install -r lab/requirements.txt",
        "#   python -m unittest discover -s tests && python -m mesh_lab experiment --output evidence/<name> --blocks 30",
        "python3 exp/analyze.py                   # writes exp/results/summary.json",
        "python3 wp/figures.py && python3 wp/build.py && node wp/katex_render.cjs wp/paper.src.html wp/paper.html",
        "node wp/pdf.cjs wp/paper.html wp/cover.pdf wp/body.pdf && python3 wp/merge_pdf.py && python3 wp/build_demo.py",
    ])
    p(f"Lab evidence root for this edition: Merkle root of the settlement ledger's first epoch <code>{L['J']['root']}</code>. "
      "The artifact contains every script, the raw results, summary.json, the lab source, its evidence file, per-process event logs "
      "and transcript, the figure sources and the built outputs.")

    h2("B", "Appendix B. Notation", "appB")
    table(["Symbol", "Meaning"], [
        [ieq("n, e, d"), "RSA modulus, public and private exponent of a tier key"],
        [ieq(r"m, r, z, \hat{s}, s"), "token message, blinding factor, blinded message, blind signature, token signature"],
        [ieq("Q"), "service quantum: generated tokens one token authorises"],
        [ieq(r"\sigma_\tau, w_\tau"), "service granted to tier and tier weight"],
        [ieq(r"B_m, B_0, \beta, c_m"), "member budget, base budget, bonus rate, verified service contributed"],
        [ieq("q, d"), "audit rate; probability an audit exposes a given cheat"],
        [ieq("g, L"), "gain per cheated request; loss on detection"],
        [ieq("W, N"), "witnesses; ledger entries in an epoch"],
        [ieq("a, n_s, r, S"), "device availability, devices enrolled per stage, required candidates per stage, remote stages"],
    ])

    h2("C", "Appendix C. Authorship and disclosure", "appC")
    p("This preprint is authored by Craig Ross and Tommy Xaypanya, THOX.ai LLC, and issued by THOX.ai Research. The corresponding and accountable "
      "author is Tommy Xaypanya, Chief Technology Officer and Co-Founder (ORCID 0009-0000-4425-9565). The roster was settled by the founders on "
      "2026-11-10 and is the roster for any external submission of either paper. The companion paper and lab were prepared "
      "with a different AI system (ChatGPT, OpenAI) and are cited, reproduced and reconciled here, not merged. Generative AI assistance: the repository review, literature retrieval, experiment and lab code, analysis, figures "
      "and draft text were produced by an AI system (Claude, Anthropic) operating as the THOX digital human Odette Lark under the "
      "direction of the corresponding author. Every arXiv entry was resolved against the arXiv API, every RFC against the RFC "
      "Editor's record and every venue page was opened on 2026-11-10; every number is generated from the experiment and lab outputs. "
      "No AI system is an author. Conflicts: the author is a THOX.ai principal and MeshStack is a THOX.ai product; this is an "
      "interested-party technical account. External submissions proceed under the founders' standing approval recorded on 2026-11-04.")

DIGEST_HITS = sum(c["digest_detect_prompts"] for c in CH.values())
TOKEN_HITS = sum(c["token_detect_prompts"] for c in CH.values())
CHEATED = NP * len(CH)
MINT_MS = T["client_ms_2048"] + T["issuer_ms_2048"]
LAB_PASS = sum(L["summary"].values())
CHEAT_LABEL = {"skip1": "skip 1 of 10 layers", "skip3": "skip 3 of 10 layers", "skip10": "skip the whole stage",
               "fp16w": "stage weights rounded to fp16", "int8w": "stage weights quantised to int8", "noise": "0.1% Gaussian noise on the stage output"}

ABSTRACT = (
    "Most people who want to run a capable language model can afford neither the hardware nor a metered cloud account, while their "
    "neighbours' computers sit idle. This paper specifies and tests a community mesh for THOX MeshStack&trade;: members add their own "
    "devices to a shared pool, and any subscriber can run distributed inference on that pool, or reach a hosted cloud model through it, "
    "without the pool learning who is asking. The design combines blind-signed subscriber tokens (RFC 9474) and sealed envelopes through "
    "a relay (RFC 9180) for requester unlinkability; signed per-hop receipts with sampled replay audits for integrity; contribution "
    "credits that raise a member's token budget and tier, with no currency; and a witness-cosigned Merkle ledger that settles credits "
    "and penalties after the request, off the token path. We state the limit plainly: a contributor that executes a stage can read its "
    "activations, so the pool gives identity privacy, not content privacy, and requests that need the latter are refused rather than "
    f"routed. On a real {A['params_m']:.0f}M-parameter model split into three stages, a token-exact re-execution audit, the natural "
    f"choice, exposed {TOKEN_HITS} of {CHEATED} cheated requests and missed an fp16 weight substitution on all {NP} prompts; a SHA-256 "
    f"digest of the stage boundary exposed {DIGEST_HITS} of {CHEATED}. Minting an unlinkable token costs {fmt(MINT_MS, 1)} ms at "
    f"RSA-2048 and verifying one {fmt(T['verify_ms_2048'], 2)} ms; the ledger costs {fmt(BIG['build_us_per_receipt'], 2)} microseconds "
    f"per receipt. A virtual lab of {L['processes']} processes with real cryptography ran {len(L['summary'])} scenarios, including a contributor "
    f"killed mid-request, an owner reclaiming a device, a cheating contributor caught and penalised, and a forged ledger head refused "
    f"by every witness; all passed and every lab request was token-identical to the whole model. A simulation shows the cost of "
    "unlinkability for fairness: fixed issuance budgets isolate heavy users but waste capacity, and indexing issuance to pool load "
    "recovers the waste. This edition is consolidated with a companion THOX paper and lab on the same subject: we adopt its "
    "plan-wide admission rule, execution contexts and replica-first default, reproduce its 62 tests and 150-trial campaign on a "
    f"second host, and measure the replica-first claim in our own lab ({(1 - L['K']['replica_over_pipeline']) * 100:.1f}% lower "
    "per-token round trip for a whole replica than a two-stage pipeline on loopback, 30 trials each). Nothing here is a THOX "
    "device, wide-area or throughput result."
)

CONTENTS = [
    ("Executive summary", "exec"), ("1. Introduction", "intro"), ("2. Background and related work", "related"),
    ("3. System and threat model", "model"), ("4. Design", "design"), ("5. Implementation", "impl"),
    ("6. Evaluation", "eval"), ("7. Discussion and limitations", "limits"), ("8. Conclusion", "concl"),
    ("9. Roadmap", "roadmap"), ("Appendix A. Reproducibility", "appA"),
    ("Appendix B. Notation", "appB"), ("Appendix C. Authorship and disclosure", "appC"), ("References", "refs"),
]

cover = f"""
<section class="cover">
  <div class="cover-inner">
    <div class="eyebrow"><span>THOX.ai Research &middot; Technical report {VERSION} &middot; {DATE}</span><span class="pill">Preprint, not peer reviewed</span></div>
    <h1>{TITLE}</h1>
    <p class="deck">How MeshStack&trade; subscribers can pool their own hardware, and reach cloud models through it, without the pool learning who is asking: a design, a working virtual lab and the measurements behind both.</p>
    <p class="byline">Craig Ross and Tommy Xaypanya &middot; Corresponding author: Tommy Xaypanya, CTO and Co-Founder, THOX.ai LLC &middot; ORCID 0009-0000-4425-9565</p>
    <div class="abstract"><div class="ct">Abstract</div><p>{ABSTRACT}</p></div>
    <div class="contents"><div class="ct">Contents</div><ol>{''.join(f'<li><a href="#{a}">{t}</a></li>' for t, a in CONTENTS)}</ol></div>
    <div class="cover-foot">Your AI. Your Data. Your Rules.&trade; &middot; THOX&reg;, ThoxOS&trade;, MeshStack&trade; and ThoxWork&trade; are marks of THOX.ai LLC.</div>
  </div>
</section>
"""

# ----------------------------------------------------------------------------
# Executive summary
# ----------------------------------------------------------------------------
OUT.append('<section class="paper-body">')
h2("", "Executive summary", "exec")
p("MeshStack&trade; lets one owner pool their own devices. This report specifies the next step: a community pool that different "
  "owners contribute to and any subscriber can use, plus a path to hosted cloud models through the same private front door. It was "
  "written after a review of the five MeshStack repositories on 2026-11-10 and it reuses what they already decide: the lease and "
  "owner-protection contract of Auto Device Role Mode [@thoxRole], exact-identifier model sharing, fail-closed admission, and the "
  "decisions of record [@thoxDec]. Where the brief for this paper met an existing decision, the design stays inside the decision and "
  "says so. This edition (v1.1.0) is consolidated with the companion paper <i>MeshStack Community Compute</i> and its virtual lab "
  "[@thoxCC], prepared in parallel on the same day. Section 6.8 reproduces that lab on this host and records where the two works "
  "agree, where they differ and who decides.")
kpis = [
    (f"{DIGEST_HITS} / {CHEATED}", f"cheated requests exposed by a boundary-digest audit; a token-exact audit exposed {TOKEN_HITS} and missed fp16 weights on all {NP} prompts ({MODEL_SHORT}, six cheat classes)", "measured"),
    (f"{fmt(MINT_MS, 1)} ms", f"to mint one unlinkable subscriber token at RSA-2048 (client {fmt(T['client_ms_2048'], 2)} ms, issuer {fmt(T['issuer_ms_2048'], 2)} ms); {fmt(T['verify_ms_2048'], 2)} ms to verify; RFC 9474 test vector reproduced", "measured"),
    (f"{fmt(BIG['build_us_per_receipt'], 2)} &micro;s", f"settlement ledger cost per receipt at {BIG['receipts']:,} receipts per epoch; inclusion proof {BIG['proof_bytes']} bytes; nothing added between tokens", "measured"),
    (f"{LAB_PASS} / {len(L['summary'])}", f"virtual lab scenarios passed across {L['processes']} processes; {L['C']['token_exact']} of {L['C']['requests']} community-plane requests token-identical to the whole model", "virtual lab"),
]
OUT.append('<div class="kpis">' + "".join(f'<div class="kpi"><div class="kv">{v}</div><div class="kl">{l}</div><div class="kt">{t}</div></div>' for v, l, t in kpis) + "</div>")
callout("Product implications",
        "First, the community plane can promise that the pool does not learn who is asking. It cannot promise that the contributor "
        "running a stage does not learn what was asked, and the product must say so at the point of use; personal work stays "
        "<code>local_only</code> by default. Second, contributor receipts must carry boundary digests. Token-exactness remains the "
        "right gate for certifying a stage decomposition (decision D25) and the wrong predicate for auditing a stranger. Third, "
        "contribution can earn access without a coin: non-transferable credits raise a member's token budget and tier, which keeps "
        "decision D20 intact. Fourth, hiding the requester moves fairness from the scheduler to token issuance, and a fixed "
        f"issuance budget is expensive: in simulation it cut served tokens by "
        f"{(1 - cell(0.6, 'budget', 'served_tokens') / cell(0.6, 'vtc', 'served_tokens')) * 100:.0f}% at 0.6 load. Indexing issuance "
        "to one aggregate idle bit from the pool recovers that loss in simulation and works in the lab, but does not isolate heavy "
        "members once the pool is saturated. Fifth, prefer a whole remote replica to a partition wherever one device can hold the "
        "remote part of the model: fewer hops, fewer parties that see activations, one receipt per token. Sixth, a blockchain-like ledger belongs after the request, not inside it: a "
        "witness-cosigned log gives append-only, publicly checkable settlement for microseconds per receipt.",
        "green")

sections_1_to_5()

# ----------------------------------------------------------------------------
# 6 Evaluation
# ----------------------------------------------------------------------------
h2("6", "Evaluation", "eval")
h3("6.1 Setup and questions")
p(f"All measurements ran on one Linux container (x86_64, 2 vCPU, 7 GB RAM, Python {A['host']['python']}, PyTorch {A['host']['torch']} "
  f"on CPU). The model is {MODEL_SHORT} at revision <code>{A['revision'][:8]}</code> [@smollm], fp32, greedy decoding. Timings are "
  "medians after warm-up with the repetition count stated; nothing else ran on the host during a timed run. Results are labelled "
  "<i>measured</i>, <i>virtual lab</i>, <i>simulated</i> or <i>calculated</i>, and the labels are not interchangeable. Five questions:")
ol([
    "Which audit predicate exposes a cheating contributor, and how fast under sampling? (measured)",
    "What does requester unlinkability cost? (measured)",
    "What happens to fair admission when the pool cannot identify members? (simulated)",
    "What does a blockchain-like settlement ledger cost, and where? (measured)",
    "Does the whole protocol compose, and do its refusals refuse? (virtual lab)",
])

h3("6.2 Audit predicates on a real model")
p(f"We split the model into three ten-layer stages inside one process, serialising the residual stream to fp32 bytes at each "
  f"boundary and hashing those bytes into a receipt chain. A contributor runs the middle stage. For each of {NP} prompts we generate "
  f"{A['new_tokens']} tokens honestly and under six cheats, and ask two auditors whether they would notice: one re-executes the "
  "request and compares output tokens, the other compares the boundary digest.")
p(f"<b>Baseline sanity.</b> The staged pipeline reproduced the whole model's tokens on {A['staged_token_exact']} of {NP} prompts. "
  f"Honest boundary digests were identical across two repeats ({A['repeat_digest_equal']} of {NP}) and between two threads and one "
  f"thread ({A['one_thread_digest_equal']} of {NP}), so on this host an honest contributor is never flagged. Staging cost nothing "
  f"measurable: {fmt(A['seconds_per_request_staged'], 2)} s per request staged against {fmt(A['seconds_per_request_whole'], 2)} s whole "
  f"(medians of {A['reps']} alternating passes; the difference, {abs(A['staging_overhead_pct']):.1f}% in magnitude, is inside run-to-run spread). "
  f"With key-value caching, a request moved {fmt(A["boundary_kib_per_request"], 0)} KiB across the two boundaries.")
rows = []
for name, c in CH.items():
    fd = c["first_divergence_median"]
    rows.append([CHEAT_LABEL[name], f"{c['digest_detect_prompts']} / {NP}", f"{c['token_detect_prompts']} / {NP}",
                 "never diverged" if fd is None else f"token {fd:.0f}"])
table(["Cheat by the middle stage", "Boundary-digest audit exposes", "Token-exact audit exposes", "Median first diverging token"], rows,
      caption=f"Table 5. Measured. Per-request detectability d for two audit predicates, {NP} prompts, {A['new_tokens']} greedy tokens each. "
              "The digest audit compares against an honest replay on the same host.")
figure("fig_audit.svg", 2, f"Left: share of audited requests that expose each cheat, by predicate. Right: share exposed by a token-exact "
       f"audit as a function of how many generated tokens the auditor re-executes. Measured, {NP} prompts.")
p(f"<b>The negative result.</b> Comparing tokens exposes gross cheats immediately: any skipped layer changed the first or second "
  f"token on every prompt. It does not expose economical ones. Rounding the stage's weights to fp16 changed no output token on any of "
  f"the {NP} prompts within {A['new_tokens']} tokens, and a 0.1% output perturbation changed tokens on "
  f"{CH['noise']['token_detect_prompts']}. Int8 weights were exposed on {CH['int8w']['token_detect_prompts']} of {NP}, but the median "
  f"first divergence was token {CH['int8w']['first_divergence_median']:.0f}, so a short audit prefix misses most of them (Figure 2, "
  "right). These are exactly the substitutions a contributor has a reason to make, because they save memory or compute. MeshStack's "
  "certification gate for stage decomposition is token-exactness against the whole model (decision D25 [@thoxDec]); it is the right "
  "gate for certifying an engine and the wrong predicate for auditing a stranger. The boundary digest exposed every cheat on every "
  "prompt.")
figure("fig_detect.svg", 3, "Calculated from Proposition 2 with the measured detectabilities: probability that a contributor cheating "
       "on every request has been caught, against requests served. Digest audit has d = 1 for all six cheats; the dashed line is the "
       "token-exact audit against its weakest cheat.")
det = {r_["q"]: r_["digest_n99"] for r_ in A["requests_to_99pct"]}
p(f"With the digest predicate, sampling is cheap. At an audit rate of 5% a persistent cheat is caught with 99% probability within "
  f"{det[0.05]} requests, at 10% within {det[0.1]}, at 25% within {det[0.25]} (Figure 3). By Proposition 3, if a detected cheat "
  "forfeits 100 times what one cheated request earns, any audit rate above about 1% makes cheating unprofitable; at a ratio of 10 "
  "the rate must exceed about 9%. With the token predicate against an fp16 substitution, no audit rate suffices, because d was zero "
  "in our sample.")
callout("Recommendation",
        "Receipts carry SHA-256 digests of each stage's input and output. An audit is a replay of the boundary by a node in the same "
        "determinism class. Token comparison is kept as a certification gate only. The stake a contributor forfeits should be at "
        "least 100 requests' worth of credit so that a 5% audit rate has a wide margin.")

h3("6.3 The cost of not being known")
kat = T["kat"]
p("The blind-signature implementation reproduced RFC 9474 Appendix A.3 exactly: encoded message, blinded message, blind signature and "
  f"final signature all matched ({sum(kat.values())} of {len(kat)} checks including verification by an independent library). At "
  f"RSA-2048, over {R2048['runs']} runs, blinding took {fmt(R2048['blind']['median_ms'], 2)} ms on the client, the issuer's blind "
  f"signature {fmt(R2048['blind_sign']['median_ms'], 2)} ms, unblinding {fmt(R2048['finalize']['median_ms'], 2)} ms and verification "
  f"{fmt(R2048['verify']['median_ms'], 2)} ms; all {R2048['verified']} tokens verified. At RSA-4096 the issuer's cost rises to "
  f"{fmt(R4096['blind_sign']['median_ms'], 1)} ms ({R4096['runs']} runs). The signing arithmetic here is plain Python integers, so "
  "these are upper bounds on a native implementation. A token is one signature per request, obtained in advance, so none of this is "
  "on the token path.")
h0, h4 = T["hpke"][0], T["hpke"][-1]
p(f"Sealing a message to a recipient with HPKE adds {T['hpke_overhead_bytes']} bytes and took {fmt(h0['seal_median_us'], 0)} to "
  f"{fmt(max(h['seal_median_us'] for h in T['hpke']), 0)} microseconds across payloads from {h0['payload_bytes']} bytes to "
  f"{h4['payload_bytes'] // 1024} KiB ({h0['runs']} runs each); opening took {fmt(min(h['open_median_us'] for h in T['hpke']), 0)} to "
  f"{fmt(max(h['open_median_us'] for h in T['hpke']), 0)} microseconds. The cost is dominated by the key encapsulation, not the payload, "
  "and the medians are not monotonic in size at this scale. The envelope is paid once per hop. Against a hop that carries hundreds of "
  "kilobytes of activations and runs ten transformer layers, it is not the term that matters; the extra network hop through the "
  "relay is, and this paper does not measure it.")
figure("fig_token.svg", 4, "Measured. Left: per-phase cost of one blind-signed token (log scale). Right: HPKE seal and open time by "
       "payload size. Pure-Python big-integer arithmetic for the RSA phases; library HPKE.")

h3("6.4 Admission without identity (simulation)")
P_ = F["params"]
p(f"The simulation has {len(P_['device_rates_tok_s'])} contributor devices with abstract service rates of 8, 15 and 30 tokens per "
  f"second, each unavailable while its owner is active (mean 20 minutes active, 40 idle, so availability {P_['availability']:.2f}), "
  f"and {P_['members']} members of whom {len(P_['device_rates_tok_s'])} own the devices and two submit {P_['heavy_factor']:.0f} times "
  f"the demand of the rest ({F['heavy_demand_share'] * 100:.0f}% of all demand). Five policies see identical arrival and availability "
  f"traces: FIFO, least-served-first with counter lift (VTC-style, equal weights), the same with weights that grow with a member's "
  f"contribution, the unlinkable form in which per-member token buckets gate entry to a FIFO pool, and that form with issuance "
  f"indexed to pool load. {P_['seeds']} seeds per "
  "point, eight simulated hours each. The rates are scenario parameters, not device measurements.")
rows = []
for load in (0.6, 1.0, 1.2):
    for pol, lab in (("fifo", "FIFO"), ("vtc", "least-served-first"), ("vtc_contrib", "contribution-weighted"), ("budget", "fixed issuance budget (unlinkable)"), ("budget_load", "load-indexed budget (unlinkable)")):
        rows.append([f"{load:.1f}", lab, f"{cell(load, pol, 'contributors_p95_wait_s'):,.0f} s", f"{cell(load, pol, 'others_p95_wait_s'):,.0f} s",
                     f"{cell(load, pol, 'heavy_service_share') * 100:.1f}%", f"{cell(load, pol, 'served_tokens') / 1e6:.2f} M"])
table(["Load", "Policy", "Contributors p95 wait", "Other members p95 wait", "Heavy members' share of service", "Tokens served"], rows,
      caption=f"Table 6. Simulated. Medians over {P_['seeds']} seeds. Load is offered demand over expected pool capacity. Waits are to first service.")
figure("fig_fairness.svg", 5, f"Simulated. p95 wait for contributors and for other members, and the heavy members' share of service, "
       f"against load; median and interquartile range of {P_['seeds']} seeds. The dotted line is the heavy members' share of demand.")
p(f"Three findings. First, with identity, contribution weighting does what it should: at load 1.2 contributors' p95 wait is "
  f"{cell(1.2, 'vtc_contrib', 'contributors_p95_wait_s'):,.0f} s against {cell(1.2, 'vtc', 'contributors_p95_wait_s'):,.0f} s under equal "
  f"weights and {cell(1.2, 'fifo', 'contributors_p95_wait_s'):,.0f} s under FIFO, at a cost to other members "
  f"({cell(1.2, 'vtc_contrib', 'others_p95_wait_s'):,.0f} s against {cell(1.2, 'vtc', 'others_p95_wait_s'):,.0f} s). Second, FIFO lets two "
  f"heavy members take {cell(1.2, 'fifo', 'heavy_service_share') * 100:.0f}% of service at every load; counter-based policies cut that "
  f"only once the pool saturates ({cell(1.2, 'vtc', 'heavy_service_share') * 100:.0f}% at load 1.2).")
p(f"<b>The negative result.</b> The unlinkable budget policy isolates heavy members at every load "
  f"({cell(0.6, 'budget', 'heavy_service_share') * 100:.0f}% of service at load 0.6), but as parameterised it is a poor scheduler. It is "
  f"not work-conserving: at load 0.6 it served {cell(0.6, 'budget', 'served_tokens') / 1e6:.2f} M tokens where the others served "
  f"{cell(0.6, 'vtc', 'served_tokens') / 1e6:.2f} M, and ordinary members' p95 wait was "
  f"{cell(0.6, 'budget', 'others_p95_wait_s'):,.0f} s against {cell(0.6, 'vtc', 'others_p95_wait_s'):,.0f} s, because a member whose bucket "
  "is empty waits while devices idle. A fixed issuance rate is the wrong control.")
p(f"<b>Load-indexed issuance.</b> Letting the authority issue past the budget while the pool reports an idle device and an empty "
  f"queue removes the waste: at load 0.6 the policy served {cell(0.6, 'budget_load', 'served_tokens') / 1e6:.2f} M tokens "
  f"({cell(0.6, 'budget_load', 'surplus_tokens') / 1e6:.2f} M of them as surplus) and ordinary members' p95 wait fell to "
  f"{cell(0.6, 'budget_load', 'others_p95_wait_s'):,.0f} s. It is not a complete answer. Surplus issuance is first come, first "
  f"served, so below saturation heavy members again take their share of demand ({cell(0.6, 'budget_load', 'heavy_service_share') * 100:.0f}%), "
  f"which is harmless while capacity is spare; at load 1.2 they still take {cell(1.2, 'budget_load', 'heavy_service_share') * 100:.0f}% "
  f"against {cell(1.2, 'vtc', 'heavy_service_share') * 100:.0f}% under least-served-first, and ordinary members wait "
  f"{cell(1.2, 'budget_load', 'others_p95_wait_s'):,.0f} s at p95 against {cell(1.2, 'vtc', 'others_p95_wait_s'):,.0f} s. Unlinkable "
  "admission that matches counter-based fairness under overload remains open. Lab scenario L shows the mechanism working end to "
  "end: a member past their budget received a surplus token while the pool was idle and was refused while every route was leased.")
p(f"<b>Owner protection.</b> Across all {F['owner_returns_total']:,} simulated owner returns, the longest an owner waited for their own "
  f"device was {F['owner_delay_max_s']:.1f} s, under the one-chunk bound of {F['worst_chunk_s']:.0f} s for a 256-token chunk on the "
  "slowest device (R1). The bound is a property of the chunk size and the device, not of the policy.")

h3("6.5 The settlement ledger")
p(f"Signing a {LG['receipt_bytes']}-byte receipt took {fmt(LG['receipt_sign_us']['median'], 0)} microseconds and verifying it "
  f"{fmt(LG['receipt_verify_us']['median'], 0)} ({LG['runs']} runs); these are the only ledger-related costs paid per hop, and audits "
  f"need them regardless. Building the Merkle tree for an epoch of {BIG['receipts']:,} receipts took "
  f"{fmt(BIG['build_ms']['median'], 1)} ms ({fmt(BIG['build_us_per_receipt'], 2)} microseconds per receipt, {BIG['reps']} runs). "
  f"{BIG['witnesses']} witness cosignatures on the head took {fmt(BIG['cosign_us']['median'], 0)} microseconds to produce and "
  f"{fmt(BIG['cosign_verify_us']['median'], 0)} to verify. An inclusion proof at that size is {BIG['proof_hashes']} hashes, "
  f"{BIG['proof_bytes']} bytes, verified in {fmt(BIG['proof_verify_us']['median'], 1)} microseconds.")
figure("fig_ledger.svg", 6, "Measured. Ledger cost components on a log scale. Green bars are per hop or per receipt; grey bars are once per epoch.")
p("The structure gives what a chain would be used for here: an ordered, append-only, publicly verifiable record that the operator "
  "cannot fork unnoticed (Proposition 4) and from which every balance can be recomputed. It does so with no work between two "
  "generated tokens. What it does not give is operator-independent liveness: the log operator can stop. If that matters, a small "
  "committee can order epoch heads; the request path does not change.")

h3("6.6 Virtual lab: does it compose?")
p(f"The lab ran the full protocol across {L['processes']} processes ({L['host']['cpus']} vCPU host) and recorded one evidence file. "
  f"Table 7 lists the {len(L['summary'])} scenarios. Community-plane requests were token-identical to the whole model on {L['C']['token_exact']} of "
  f"{L['C']['requests']} prompts with {L['C']['receipts_verified']} signed receipts verified by the device, and all "
  f"{L['C']['honest_audited_steps']} hops of one honest request were replayed by the auditor in a separate process with every digest "
  "matching, so cross-process replay raised no false alarm.")
I = L["I"]["wire_matrix"]
table(["", "Scenario", "What the evidence file records", ""], [
    ["A", "Enrolment", f"{L['A']['pool_size']} devices enrolled with authority certificates and signed advertisements; self-signed certificate refused ({L['A']['forged_certificate_advert']['error']}); non-subscriber refused ({L['A']['non_subscriber_enrol']['error']}); advertisement listing a cloud-tagged model refused ({L['A']['cloud_model_tag_advert']['error']})", "pass"],
    ["B", "Tokens", f"valid token redeemed for a signed lease; second redemption {L['B']['redeem_again']}; forged signature {L['B']['forged_signature']}; cloud-audience token at the pool {L['B']['wrong_audience']}; over-budget issuance {L['B']['issue_over_budget']['error']}; <code>local_only</code> request {L['B']['local_only_class']}", "pass"],
    ["C", "Inference", f"{L['C']['token_exact']} / {L['C']['requests']} requests token-exact; {L['C']['receipts_verified']} receipts verified; {L['C']['honest_audited_steps']} honest hops audited, all match", "pass"],
    ["D", "Owner returns", f"owner of {L['D']['first_route'][0]} became active at step 8; next hop refused (owner_active); request continued on {L['D']['final_route'][0]}; output token-exact; a new lease while the owner was active avoided the device; it rejoined when the owner left", "pass"],
    ["E", "Contributor dies", f"process {L['E']['killed']} killed at step 12; upstream stage reported downstream_failed naming {L['E']['killed']}; rerouted to {L['E']['final_route'][1]}; output token-exact", "pass"],
    ["F", "Cheating contributor", f"digest audit exposed noise, fp16 and skipped-layer cheats at the first audited hop, while the noise and fp16 cheats left the unaudited output token-exact; with a sampled audit at q = {L['F']['sampled_audit_rate']}, the cheat was caught at step {L['F']['detected_at_step']}, the fraud proof accepted, the node suspended, its owner's credit set to zero, and the request restarted on another node with token-exact output", "pass"],
    ["G", "Admission", f"contributor's contributor-tier budget {L['G']['contributor_contrib_budget']} tokens, consumer's {L['G']['consumer_contrib_budget']}; 8 base-tier and {L['G']['submitted']['contrib']} contributor-tier requests granted in the order " + " ".join(t[0] for t in L['G']['grant_order']) + f"; heavy member's extra issuance {L['G']['heavy_member_over_budget']['error']}", "pass"],
    ["H", "Cloud plane", f"request served through the relay with label <code>{L['H']['plane_label']}</code> and the notice that the provider can read the prompt; token replay {L['H']['token_replay']}; community-class request {L['H']['community_class_at_cloud']}", "pass"],
    ["I", "Information flow", f"across {I['relay']['inbound_bytes'] / 1e6:.0f} MB received by the relay, {I['B1']['inbound_bytes'] / 1e6:.0f} MB by the busiest stage node and everything received by the coordinator, auditor and gateway, no consumer account, token value or prompt text appeared on the wire; the authority received accounts and no token value", "pass"],
    ["K", "Replica route", f"a contributor joined mid-run holding both remote layer ranges ({L['K']['joined_mid_run']['params_held'] / 1e6:.1f}M parameters) and was leased as a whole replica; {L['K']['attempts']} of {L['K']['completed']} requests completed across both topologies, all token-exact; replica hops audited, all match (timing in Section 6.7)", "pass"],
    ["L", "Load-indexed issuance", f"member past budget, pool idle: token issued and marked surplus; every route leased: {L['Lx']['over_budget_while_busy']['error']}; routes released: issued again; contributor-tier surplus refused", "pass"],
    ["J", "Ledger", f"{L['J']['entries']} coordinator-signed records sealed in one epoch; {L['J']['witness_cosignatures_valid']} of {L['J']['witnesses']} witness cosignatures valid; balances replayed from the log equal the authority's; inclusion proof for the penalty record valid ({L['J']['inclusion_proof_hashes']} hashes) and invalid after a one-character change; a forged head for the same epoch cosigned by {L['J']['fork_attempt']['cosigned_by']} witnesses; next epoch chains to the first", "pass"],
], caption="Table 7. Virtual lab. Every cell is generated from lab/evidence/evidence.json. A scenario passes only if every listed condition held.")
p("Two observations from the lab belong in the design. First, scenario F reproduced the audit finding end to end: a contributor "
  "that perturbed or down-cast its output produced a response the requester could not distinguish from an honest one, and was still "
  "caught at the first audited hop. Second, scenario I is a statement about the wire, not about knowledge. Stage nodes decrypt "
  "activations and the gateway decrypts the prompt, by design. The scan shows that the relay, which holds no key, and the "
  "coordinator, which holds only its own, receive nothing readable that identifies a consumer.")
p(f"Lab timings are not performance results. A hop took a median of {L['C']['hop_ms_median']:.0f} ms and a {L['C']['new_tokens_each']}-token "
  f"request {L['C']['seconds_per_request_median']:.1f} s, on stateless hops that recompute the whole sequence at every step, over "
  f"loopback, with {L['processes']} processes sharing two cores.")

h3("6.7 Topology: whole replica against pipeline")
KP, KR, NW = L["K"]["pipeline"], L["K"]["replica"], S["network"]
p(f"<b>Measured in the lab.</b> In scenario K a third contributor joined mid-run holding both remote layer ranges, and the "
  f"requester alternated between the two-stage pipeline route and the whole-replica route in ABBA order: {KP['trials']} trials "
  f"each of {L['K']['tokens_per_trial']} generated tokens, one labelled warm-up per topology kept in the record, nothing "
  f"discarded. The mean remote round trip per token was {KP['mean_ms']:.1f} ms for the pipeline (95% bootstrap interval "
  f"{KP['ci95_ms'][0]:.1f} to {KP['ci95_ms'][1]:.1f}; trial-mean CV {KP['cv_percent']:.1f}%) and {KR['mean_ms']:.1f} ms for the "
  f"replica ({KR['ci95_ms'][0]:.1f} to {KR['ci95_ms'][1]:.1f}; CV {KR['cv_percent']:.1f}%), a reduction of "
  f"{(1 - L['K']['replica_over_pipeline']) * 100:.1f}%. The intervals do not overlap and both CVs are under the 10% dispersion "
  "condition of decision D37, which is necessary and not sufficient for a claim-grade number: this is one host, loopback, a small "
  "model and stateless hops. The saving here is one sealed hop and one receipt; the layers computed are the same.")
p(f"<b>Calculated for real links.</b> The companion paper models one serial decode stream as compute plus per-link delay plus "
  f"bytes over goodput [@thoxCC]. We re-derived its four-stage example and obtained the same cycle times "
  f"({', '.join(f'{x:.2f}' for x in NW['companion_table5_reproduced_ms'])} ms). Applying the same form to this design, with "
  f"{NW['compute_s_assumed'] * 1e3:.0f} ms of assumed total compute per token, a sealed fp32 position of {NW['hidden_position_bytes']:,} "
  f"bytes for the test model, {NW['receipt_bytes']} bytes per signed receipt, six link traversals per token for the pipeline through "
  "the relay and four for a replica through the relay, gives Table 8. On a wide-area link the relay and the extra stage dominate: "
  "delay, not payload, is the term that matters at this hidden size.")
table(["Link assumption", "One-way delay, goodput", "Pipeline via relay", "Whole replica via relay", "Replica advantage"], [
    [r_["link"], f"{r_['one_way_ms']:.0f} ms, {r_['mbps']:,.0f} Mbps", f"{r_['pipeline_ms']:.1f} ms ({r_['pipeline_tok_s']:.2f} tok/s)",
     f"{r_['replica_ms']:.1f} ms ({r_['replica_tok_s']:.2f} tok/s)", f"{(r_['replica_tok_s'] / r_['pipeline_tok_s'] - 1) * 100:.0f}%"]
    for r_ in NW["rows"]],
    caption="Table 8. Calculated, not measured. One sequence, no queueing, jitter, batching or speculation. The compute figure is an "
            "assumption held constant; it is not a THOX device rate. A hosted whole model that streams tokens pays the link once per "
            "request, not once per token.")
figure("fig_topology.svg", 7, f"Left: measured remote round trip per token in this lab, pipeline against whole replica, mean and 95% "
       f"bootstrap interval of {KP['trials']} trials each. Centre: calculated single-stream rate by link class (Table 8). Right: the "
       "companion lab's inter-token interval by configuration, as retained by its authors and as reproduced on this host.")
callout("Recommendation",
        "Route to a whole replica when one eligible device can hold the remote layers. Admit a cross-device partition only for a "
        "model that no single eligible device can hold, within a nearby group first, and only after measuring it. This matches the "
        "companion paper's default and the earlier household report's sequencing [@thoxCC; @thoxP1].")

h3("6.8 The companion paper and lab: reproduction and reconciliation")
CR, CP = S["companion"]["retained"], S["companion"]["reproduction"]
p(f"The companion work [@thoxCC] approaches the same problem from the governance side: who may process what, under which "
  f"consent, with which evidence. Its lab runs six worker processes with mutual TLS and pinned certificates, per-call HMAC grants "
  f"bound to the request body, tenant namespaces, transactional settlement and a signed, hash-linked receipt log, on an untrained "
  f"{CR['parameters']:,}-parameter float64 model under one trusted operator. Ours assumes hostile contributors and an anonymous "
  "requester on a trained model. The two labs test different things and neither subsumes the other.")
p(f"<b>Reproduction.</b> We ran the companion lab unmodified on this host with its pinned dependencies under Python "
  f"{CP['python']}: 62 of 62 tests passed (43 unit, 19 integration). Its full campaign completed {CP['trial_count']} of "
  f"{CR['trial_count']} trials plus {CP['warmups']} warm-ups, every trial numerically equal to its reference, "
  f"{CP['scenario_passes']} of {CP['scenario_count']} policy and fault scenarios passed, and the signed log verified with "
  f"{CP['receipts']} receipts, the same count its authors retained. The experiment plan hash and the model fingerprint are "
  "identical to the retained run, so the same model bits and the same plan ran on a different machine.")
rows = []
for a_, b_ in zip(CR["configurations"], CP["configurations"]):
    rows.append([a_["configuration"].replace("_", " "), f"{a_['mean_inter_token_ms']:.2f} ms", f"{a_['inter_token_trial_mean_cv_percent']:.1f}%",
                 f"{b_['mean_inter_token_ms']:.2f} ms", f"{b_['inter_token_mean_ci95_ms'][0]:.2f} to {b_['inter_token_mean_ci95_ms'][1]:.2f}",
                 f"{b_['inter_token_trial_mean_cv_percent']:.1f}%", f"{b_['numerically_equal']} / {b_['completed']}"])
table(["Configuration", "Authors' host: mean inter-token", "CV", "This host: mean inter-token", "95% interval", "CV", "Numerically equal"], rows,
      caption="Table 9. Companion lab timing, 30 trials per configuration, as retained by its authors (Python 3.12.14) and as reproduced "
              f"here (Python {CP['python']}, 2 vCPU). Observed on one host each; not a performance claim for either.")
p("<b>What the reproduction adds.</b> The ordering and the effect of injected delay reproduce: the whole replica is several times "
  "faster per token than the four-stage pipeline, and each added wait per call raises the interval. The dispersion does not "
  f"reproduce: the authors reported that every configuration exceeded the 10% CV condition (up to "
  f"{max(c['inter_token_trial_mean_cv_percent'] for c in CR['configurations']):.0f}%), while on this host every configuration is "
  f"under it (at most {max(c['inter_token_trial_mean_cv_percent'] for c in CP['configurations']):.1f}%). The noise was a property "
  "of their host, not of the lab. Neither run qualifies a performance statement. The comparison of an active and a paused audit "
  f"writer also reproduces as no detectable difference ({CP['configurations'][1]['mean_inter_token_ms']:.2f} ms against "
  f"{CP['configurations'][4]['mean_inter_token_ms']:.2f} ms, overlapping intervals), which supports both papers' position that "
  "settlement belongs off the token path.")
p("<b>A portability defect.</b> Under Python 3.13 the companion lab's 43 unit tests pass and its integration tests cannot start: "
  "the default TLS context in 3.13 verifies strictly and rejects the lab's generated certificates for a missing Authority Key "
  "Identifier. The lab documents Python 3.12 and works there. The certificates should carry subject and authority key "
  "identifiers before the lab is used on a current interpreter.")
table(["Topic", "Companion paper", "This paper", "Status"], [
    ["Trust model", "one trusted operator; contributors approved", "hostile contributors; anonymous requester", "complementary; both labs kept, never merged into one result"],
    ["Model in the lab", "untrained 241,280-parameter float64 fixture", f"trained {A['params_m']:.0f}M-parameter {MODEL_SHORT}, fp32", "complementary"],
    ["Requester identity", "tenant-scoped pseudonym known to the coordinator", "blind token; coordinator never learns the account", "<b>settled 2026-11-10, composed.</b> The tenant pseudonym is the accounting and quota identity at the coordinator; the blind token is the requester-facing execution credential, so fairness is enforced at issuance against the pseudonym and execution stays unlinkable (Section 6.4)."],
    ["Default topology", "whole replicas first; partitions only where measured", "pipeline assumed in v1.0.0", "adopted from the companion in this edition; measured in Section 6.7"],
    ["Admission", "plan-wide eligibility rule and plan digest", "per-hop lease checks", "adopted; the lease now carries a plan digest"],
    ["Confidential context", "refused without an attested boundary", "not modelled in v1.0.0", "adopted; refused in lab scenario B"],
    ["Transport between hosts", "mutual TLS with pinned certificates, HMAC grant per call", "HPKE sealing per message, signed lease", "both valid; production should use the tunnel and identities MeshStack already has, plus per-message sealing through the relay"],
    ["Integrity of a host's work", "receipt records the action; not proof of honest computation", "boundary-digest replay audit and fraud proofs", "this paper adds the audit; the companion states the gap"],
    ["Settlement", "transactional outbox, signed hash-linked batches, retained checkpoint", "Merkle epochs, witness cosignatures, replay", "compatible. The companion's outbox and idempotency should feed this paper's witnessed log; the companion notes a signed prefix cannot detect a dropped suffix without an outside checkpoint, which witnesses provide"],
    ["Contribution accounting", "credits and settlement are a new product decision", "non-transferable credits raise token budget and tier", "agree that it needs a decision; D20 stands until then"],
    ["Byline", "Craig Ross and Tommy Xaypanya", "Craig Ross and Tommy Xaypanya", "<b>settled 2026-11-10.</b> One roster for both papers: Craig Ross first author, Tommy Xaypanya corresponding author; this edition carries it"],
], caption="Table 10. Reconciliation of the two works. Nothing was merged silently; where they differ, the difference and its owner are named.")

sections_7_to_end()
# ----------------------------------------------------------------------------
# References
# ----------------------------------------------------------------------------
h2("", "References", "refs")
refs_html = []
for i, key in enumerate(CITED, 1):
    r = ref_entry(key)
    authors = ", ".join(r["authors"])
    link = f' <a href="{r["url"]}">{r["url"]}</a>' if r["url"] else ""
    refs_html.append(f'<li id="ref{i}"><span class="rn">[{i}]</span> {html.escape(authors)}. <i>{html.escape(r["title"])}</i>. {html.escape(r["venue"])}.{link}</li>')
OUT.append('<ol class="refs">' + "".join(refs_html) + "</ol>")
OUT.append("</section>")

# ----------------------------------------------------------------------------
# Page
# ----------------------------------------------------------------------------
CSS = """
/*__FONTS__*/
/*__KATEX__*/
:root{--green:#047C3D;--green-dark:#05A451;--ink:#111827;--muted:#6B7280;--rule:#E5E7EB;--pale:#E6F4EC;--bg:#FFFFFF}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--bg);color:var(--ink);font-family:Inter,system-ui,sans-serif;font-size:10.5pt;line-height:1.5}
.cover{background:#0B0F14;color:#F3F4F6;min-height:100vh;padding:0}
.cover-inner{max-width:7.1in;margin:0 auto;padding:0.9in 0.6in 0.6in}
.eyebrow{display:flex;justify-content:space-between;align-items:center;font-family:'JetBrains Mono',monospace;font-size:8pt;color:#9CA3AF;border-bottom:1px solid #1F2937;padding-bottom:8px}
.pill{border:1px solid var(--green-dark);color:var(--green-dark);border-radius:999px;padding:2px 10px}
.cover h1{font-size:21pt;line-height:1.2;font-weight:700;margin:22px 0 10px;color:#fff}
.deck{font-size:11pt;color:#D1D5DB;margin:0 0 10px}
.byline{font-size:8.5pt;color:#9CA3AF;margin:0 0 16px}
.abstract{border-left:3px solid var(--green-dark);padding:4px 0 4px 12px;margin:10px 0 14px}
.abstract p{font-size:9.2pt;line-height:1.45;color:#E5E7EB;margin:4px 0 0}
.ct{font-family:'JetBrains Mono',monospace;font-size:8pt;letter-spacing:.08em;text-transform:uppercase;color:var(--green-dark)}
.contents ol{columns:2;column-gap:28px;font-size:8.6pt;margin:6px 0 0;padding-left:0;list-style:none;color:#D1D5DB}
.contents a{color:#D1D5DB;text-decoration:none}
.cover-foot{margin-top:18px;font-size:8pt;color:#6B7280;border-top:1px solid #1F2937;padding-top:8px}
.paper-body{max-width:7.1in;margin:0 auto;padding:0.5in 0.6in 0.8in}
@media screen{.paper-body{padding-top:0.6in}}
h2{font-size:14pt;font-weight:700;margin:26px 0 8px;padding-bottom:4px;border-bottom:2px solid var(--green);break-after:avoid}
h2 .num{color:var(--green);margin-right:10px;font-family:'JetBrains Mono',monospace;font-size:11pt}
h3{font-size:11pt;font-weight:600;margin:16px 0 6px;break-after:avoid}
p{margin:0 0 8px;text-align:left}
.cite{color:var(--green);font-size:9pt}
table{width:100%;border-collapse:collapse;font-size:8.4pt;margin:8px 0 12px;break-inside:auto}
caption{caption-side:bottom;text-align:left;font-size:8.2pt;color:var(--muted);padding-top:5px}
th{background:var(--ink);color:#fff;text-align:left;padding:5px 6px;font-weight:600;font-size:8pt}
td{padding:4px 6px;border-bottom:1px solid var(--rule);vertical-align:top}
tr{break-inside:avoid}
figure{margin:12px 0 14px;break-inside:avoid}
.figwrap svg{width:100%;height:auto}
figcaption{font-size:8.4pt;color:var(--muted);margin-top:4px}
.eq{margin:6px 0 8px;text-align:center;font-size:10pt;overflow-x:auto}
.callout{border-left:3px solid var(--green);background:var(--pale);padding:8px 12px;margin:10px 0 12px;font-size:9.5pt;break-inside:avoid}
.callout .ct{margin-bottom:3px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:10px 0 12px}
.kpi{border:1px solid var(--rule);border-top:3px solid var(--green);padding:8px 9px;break-inside:avoid}
.kv{font-family:'JetBrains Mono',monospace;font-size:17pt;font-weight:700;color:var(--green);line-height:1.1}
.kl{font-size:8pt;color:var(--ink);margin-top:4px;line-height:1.3}
.kt{font-family:'JetBrains Mono',monospace;font-size:7pt;color:var(--muted);text-transform:uppercase;margin-top:5px;letter-spacing:.06em}
.algo{border:1px solid var(--rule);margin:8px 0 12px;break-inside:avoid}
.algo .at{background:var(--ink);color:#fff;font-size:8.4pt;font-weight:600;padding:4px 8px}
.algo pre,pre.small{font-family:'JetBrains Mono',monospace;font-size:7.8pt;line-height:1.4;margin:0;padding:8px;white-space:pre-wrap;overflow-x:auto}
pre.small{border:1px solid var(--rule)}
code{font-family:'JetBrains Mono',monospace;font-size:8pt;word-break:break-all}
ol,ul{margin:0 0 8px;padding-left:20px}
li{margin:0 0 4px}
.arch{border:1px solid var(--rule);padding:10px;margin:8px 0 2px;font-size:7.8pt;break-inside:avoid}
.arch-row{display:grid;gap:8px;margin:0}
.arch-row.three{grid-template-columns:1fr 1.3fr 1fr}.arch-row.four{grid-template-columns:repeat(4,1fr)}.arch-row.two{grid-template-columns:1fr 1fr}
.arch-arrow{text-align:center;color:var(--muted);font-family:'JetBrains Mono',monospace;font-size:7pt;padding:4px 0}
.box{border:1px solid var(--ink);border-radius:4px;padding:6px 8px;background:#fff}
.box b{display:block;font-size:8.2pt;margin-bottom:2px}.box span{color:#374151}
.box.hi{background:var(--pale);border-color:var(--green)}.box.ghost{background:#F3F4F6;border-color:#9CA3AF}.box.dim{border-style:dashed}
.refs{font-size:8.3pt;padding-left:0;list-style:none}
.refs li{margin:0 0 5px;padding-left:28px;text-indent:-28px}
.refs .rn{font-family:'JetBrains Mono',monospace;color:var(--green);margin-right:4px}
.refs a{color:var(--green);word-break:break-all;text-decoration:none}
@media print{.cover{min-height:11in;height:11in}h2{page-break-after:avoid}}
@media (max-width:600px){.paper-body,.cover-inner{padding:24px 16px}.cover h1{font-size:17pt}.kpis{grid-template-columns:1fr 1fr}.arch-row.three,.arch-row.four,.arch-row.two{grid-template-columns:1fr}.contents ol{columns:1}table{display:block;overflow-x:auto;white-space:normal}.eq{font-size:8.5pt}pre{font-size:7pt}.refs a{word-break:break-all}}
"""

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(SHORT)}</title>
<meta name="description" content="THOX.ai Research technical report {VERSION}">
<style>{CSS}</style></head>
<body data-version="{VERSION}">
{cover}
{''.join(OUT)}
</body></html>"""

out = ROOT / "wp" / "paper.src.html"
out.write_text(page)
print("wrote", out, "cited", len(CITED), "refs")
unused = [k for k in list(REFS_RAW) + list(MANUAL_REFS) if k not in CITED]
print("uncited keys (not listed):", unused)
em = page.count("—")
print("em dashes:", em)
