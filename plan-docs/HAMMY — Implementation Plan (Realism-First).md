# HAMMY — Implementation Plan (Realism-First)

*Companion to the HAMSTER Technical Blueprint. Assumes one developer, roughly 15–20 hours per week, an RTX 5070 laptop (8 GB VRAM, 32 GB RAM), and a mostly free or low-cost cloud budget. Time estimates are planning guesses, not measurements. Re-baseline them after each phase.*

## 1. The honest realism target

"No visible difference from a real hamster" is the right ambition, but it needs to be split into what is achievable and where.

| Level | What it means | Achievable? |
| --- | --- | --- |
| A. Offline cinematic | Blender Cycles renders with hair curves, subsurface scattering, depth of field. Stills and short clips that most people can't tell from video. | Yes, with serious asset work. |
| B. Real-time, high-end | A strand or shell fur hamster in a browser (WebGPU) or a desktop engine. Convincing at normal viewing distance, with close-ups revealing it is CG. | Mostly yes. This is the practical ceiling for the live view. |
| C. Real-time, indistinguishable in macro close-up | Per-hair lighting, wet nose, whisker motion, fur clumping under real contact. | Not on a laptop browser today. Film studios use hours per frame for this. |

**Decision:** a two-tier rendering strategy.

1. **Live view (Level B):** real-time, as good as the platform allows.
2. **Moments (Level A):** milestones, first discoveries, and daily highlights are rendered offline with Cycles from the logged trajectory and delivered as video clips (Telegram, Memory screen). This is where "indistinguishable" is realistic.

The biggest realism killer is usually **motion and behaviour**, not fur. A photoreal hamster that moves like a game character reads as fake within a second. A slightly less detailed hamster that moves exactly like a real one reads as real. The plan therefore spends as much effort on motion as on appearance.

## 2. Key decisions up front

| Decision | Recommendation | Why |
| --- | --- | --- |
| Species | Syrian (golden) hamster, adult, \~12–17 cm body, \~100–150 g | Large enough to model, abundant reference footage, distinctive cheek pouches and loose skin |
| Live renderer | Three.js with WebGPU (WebGL2 fallback) | Matches your stack. Verify browser support at build time. |
| Optional desktop renderer | Unreal Engine 5 (strand-based Groom) as a local "showcase mode" | Far better fur, but it can't be hosted cheaply or run in the browser. Defer. |
| Physics body vs. visual body | Two separate rigs: a simple physics skeleton and a detailed visual skeleton | Keeps RL tractable while the visuals stay rich |
| Backend clock | Lazy catch-up plus a scheduled tick every few minutes | No always-on worker needed |
| Early agent body | Simplified body first, quadruped later (see Phase 1) | Avoids blocking everything on locomotion |
| RL stack for legged control | MJX / MuJoCo Playground or an Isaac-style GPU-parallel setup plus rsl\_rl or skrl | Stable-Baselines3 on CPU MuJoCo will be too slow |

## 3. Revised architecture

The blueprint's component list stays. Four changes:

1. **Motion layer between physics and rendering.** The physics sim outputs body pose, foot contacts, and velocity. A retargeting layer maps these onto the detailed visual rig and adds the secondary motion physics doesn't model (see Section 4.2).
2. **Skill-outcome models for background life.** While the browser is closed, the hamster does not run a fake timer. The high-level policy picks skills, and each skill's outcome (success, duration, energy cost, collision risk) is sampled from empirical distributions collected from thousands of headless MuJoCo episodes. Every event is tagged `observed_physics`, `sampled_from_skill_model`, or `rule`.
3. **Episode clips for live viewing.** The server produces short trajectory clips (keyframes plus contacts) that the client replays and interpolates. Streaming 50 Hz physics to every viewer is expensive and fragile.
4. **Seeded determinism.** Every episode stores its RNG seed so "what happened while I was gone" can be replayed and verified, including re-rendered offline in Cycles.

## 4. The realism pipeline

### 4.1 Visual appearance

**Modelling**

- Sculpt the body in Blender (or ZBrush if available) from reference photos and, ideally, real proportions: stout body, short tail, large cheek pouches, small ears, dark eyes, five hind toes and four front toes.
- Model the cheek pouches as blend shapes (empty to full). This is a signature hamster behaviour and a strong realism cue.
- Retopologise to a real-time budget (target roughly 30–60k triangles for the body, with a lower LOD for distance).
- Separate meshes for eyes, teeth (continuously visible incisors), whiskers, claws, and tongue.

**Fur (the hard part)** Options, from cheapest to richest:

| Technique | Quality | Cost | Notes |
| --- | --- | --- | --- |
| Shell texturing | Good at a distance | Low | Works in WebGL2. Silhouettes look soft. |
| Shells plus hair-card fins at the silhouette | Good to very good | Low to medium | The best browser compromise |
| Strand rendering via WebGPU compute | Very good | High | Experimental in Three.js. Needs a prototype benchmark. |
| Strand-based Groom in Unreal Engine | Excellent | High, desktop only | Showcase mode |

Plan: build the Blender groom first with hair curves (guide hairs plus interpolation, length and direction maps, undercoat and guard-hair layers, colour variation). Bake it down to shells plus fins for the browser. Keep the full groom for Cycles moments.

**Materials and lighting**

- Subsurface scattering approximation on ears, nose, and paws.
- Wet specular on the nose and eyes, plus a corneal reflection (eyes are the first thing viewers check).
- Image-based lighting from a real HDRI, soft shadows, ambient occlusion, and subtle depth of field.
- Fur rim lighting (backlit translucency is what makes fur read as fur).

**Texture work**

- Albedo and roughness painted from reference. Add per-hair colour variation, a belly and chest colour change, and slightly dirty or oily fur patches over time.

### 4.2 Motion realism (biggest lever)

1. **Physics skeleton:** a simple articulated body for RL (add 2–3 spine joints to the 12 leg joints, since real hamsters bend their spines a lot when turning and digging).
2. **Visual skeleton:** 60–100 bones including spine chain, shoulders and hips, head, jaw, ears, whiskers, tail, toes. The physics output drives the main body and feet. Procedural layers add the rest:
   - Whisker twitching at 5–10 Hz while sniffing, with whiskers sweeping forward when investigating.
   - Ear rotation toward sounds and objects.
   - Nose and sniff cycles.
   - Breathing (visible flank movement).
   - Head micro-saccades and blink rate.
   - Fur secondary motion (jiggle on the loose skin, wind-free sway via spring bones).
3. **Style from real animals:** collect hamster video (your own, or freely licensed footage; check licensing) and extract keypoints with a pose-estimation tool such as DeepLabCut or SLEAP. Use these as reference motion for an **adversarial motion prior** (AMP-style style reward) so the learned gait *looks* like a hamster's rather than a generic quadruped. Treat this as a research experiment with a fallback (plain RL gait plus hand-tuned style rewards).
4. **Hamster-specific behaviours to model explicitly** (each is a skill with its own animation and physics treatment):
   - Cheek stuffing and unloading, with visible pouch inflation.
   - Standing on hind legs to scan.
   - Grooming sequences (face wash, flank, hind-leg scratch).
   - Digging and burrowing in deformable bedding.
   - Wheel running (gait on a curved moving surface).
   - Nest building and carrying material.
   - Curl-up sleeping and slow breathing.
   - Startle response and freeze.
5. **Timing realism:** real hamsters are crepuscular and nocturnal. Build a circadian activity schedule into the drives so it sleeps most of the day. Viewers will accept an idle hamster far more readily than one that runs constantly.

### 4.3 Habitat realism

- PBR materials for wood, plastic, metal bars or glass, and bedding.
- Bedding as a heightfield or particle system that deforms under paws and supports burrow tunnels. Accept a simplified contact model in physics and a richer visual one.
- Food items as small physical objects with believable textures (seeds, pellets). Water bottle with droplet and meniscus effects.
- Dust motes, soft shadows, and light changing with a simulated day cycle.

### 4.4 Audio

- Wheel squeak and rattle, seed cracking, bedding rustle, tiny footsteps, squeaks, and sniffing. Audio sells realism more cheaply than pixels. Use licensed or self-recorded samples.

### 4.5 Realism validation

- Run a blind A/B test: short clips of the real hamster and HAMMY, shown to 15–30 people who guess which is real. Track the percentage who can tell. Do this separately for stills, live-view clips, and Cycles moments.
- Track a motion-realism score against reference footage (gait cycle timing, speed, turning radius, pause and sniff frequency).
- The goal metric is "viewers guess at close to chance" for Level A moments and "most viewers fooled at normal distance" for the live view. Don't claim more than the test shows.

## 5. The AI plan (kept honest)

**5.1 High-level behaviour as a semi-Markov decision process over skills**

- Skills: approach food, eat, drink, hoard, explore area, enter tunnel, use wheel, groom, nest, rest, hide.
- The high-level policy chooses a skill given drives, memory features, and context. Each skill has a termination condition.

**5.2 Drives via homeostatic RL**

- State: hunger, thirst, energy, comfort, stress, curiosity, plus a circadian phase.
- Reward is the reduction in deviation from each set point, so trade-offs between needs emerge rather than being hand-weighted.
- Log each drive's time-in-healthy-range as a headline metric.

**5.3 Memory that changes decisions**

- Per-object value estimates with confidence and decay.
- Spatial familiarity map and route statistics.
- Recency features feed the high-level policy as inputs.
- Event memories remain in PostgreSQL for the Observatory, but only features that actually influence the policy count as learned memory.

**5.4 Curiosity**

- Try RND first (simpler than ICM). Compare against a no-curiosity baseline. Use novelty decay to avoid noisy-TV traps.

**5.5 Autonomy report (the proof)** In the Training Lab, publish for every release:

- Memory on vs. off.
- Curiosity on vs. off.
- Homeostatic performance across at least 5 seeds.
- Routine formation and behavioural diversity over simulated days.
- Adaptation after the habitat is rearranged.

World models and hierarchical learned option discovery stay as research stretch goals. Add one only if it beats the baseline.

## 6. Persistence and infrastructure

- **Source of truth:** PostgreSQL (Supabase) with an append-only `world_events` table, `pet_state` snapshots with optimistic concurrency, and idempotency keys on every command.
- **World advancement:** a scheduled tick every few minutes (pg\_cron, a Supabase scheduled function, or a small cron service) plus on-demand catch-up when the parent opens the app. This avoids paying for an always-on worker. Check current free-tier sleep and execution limits for your chosen host before committing.
- **Catch-up:** bounded chunks, skill-outcome sampling, a summary event, and no loop over every second.
- **Leases:** a database lease per pet so retries never double-advance the world.
- **Telegram:** start with polling or a webhook through the same authenticated command handlers as the site. Daily digest plus rare "moments" (with Cycles-rendered clips when available).
- **Object storage:** model files, trajectory clips, rendered moment videos. Set a retention policy, since video accumulates fast.
- **Neglect policy:** no death in v1. Gradual degradation (lower comfort, withdrawn behaviour) and escalating but rate-limited reminders.
- **Pause and kill switch:** visible pause state and a system-level stop for workers.
- **Backups:** scheduled database backups and one tested restore.

## 7. Compute plan

1. **Fix PyTorch for Blackwell first.** The RTX 5070 needs a PyTorch build with CUDA 12.8 or newer. Verify with a one-line GPU test before anything else.
2. **Benchmark before committing.** Measure MuJoCo CPU steps per second and MJX GPU steps per second with a toy quadruped. This decides the training stack.
3. **WSL2 or Linux** is likely the smoothest route for GPU-parallel RL tooling on Windows. Test early.
4. **8 GB VRAM** limits parallel environments and network sizes, not feasibility. Locomotion policies are small. Plan for modest batch sizes.
5. **Offline rendering** (Cycles) will compete with training for the GPU. Schedule them separately.
6. **Heavy fur and 3D testing** should include a mid-range phone and a mid-range laptop, since the parent will open the site on a phone.

## 8. Phased plan with time boxes

Time boxes assume 15–20 hours per week. Each phase has an exit test and a kill criterion.

### Phase 0 — Foundations (1–2 weeks)

- Verify PyTorch and CUDA on the 5070, MuJoCo install, and MJX benchmark.
- Read the Microduck runtime and RL repositories directly and check each license. (They were only attached as links, so I haven't inspected them.)
- Set up the monorepo, contracts folder, and a decision log.
- Collect and organise real hamster reference footage and photos.
- **Exit:** a toy MuJoCo env steps at a measured speed, and the GPU is confirmed in PyTorch.

### Phase 1 — Vertical slice with a simplified body (3–4 weeks)

- Point-mass or simple wheeled-style agent in the MuJoCo habitat with velocity commands.
- Drives with homeostatic reward, small skill library, high-level policy, per-object memory.
- Habitat with bowl, water, hideout, tunnel placeholder.
- **Exit:** the agent satisfies its drives across 100+ simulated days of headless episodes with a measured time-in-range.
- **Kill criterion:** if homeostasis doesn't emerge by week 5, simplify the reward and drive set before adding anything.

### Phase 2 — Persistence, Telegram, minimal Observatory (3 weeks)

- Postgres schema, leases, idempotent commands, catch-up with skill-outcome models.
- Scheduled ticks, Telegram digest and `/status`, `/feed`, `/pause`.
- Minimal Observatory showing active goal, drives, and recent events.
- **Exit:** close everything, wait, return, and see a correct, replayable event history. Restart the worker mid-update without duplicates.

### Phase 3 — Hero asset: first realistic hamster (6–10 weeks, runs in parallel with Phase 1–2 from week 3)

- Sculpt and retopologise the body, groom in Blender, build the visual rig and blend shapes.
- Prototype three fur options in the browser (shells, shells plus fins, WebGPU strands) and benchmark frame rate on laptop and phone.
- Build five core animations (idle, sniff, walk, groom, sleep) with the procedural layers.
- **Exit:** blind A/B test on stills and a short walking clip. Record the result honestly.
- **Kill criterion:** if no fur option holds 30 fps on a mid-range laptop, ship shells plus fins and move the richer fur to offline moments.

### Phase 4 — Learned locomotion (4–8 weeks)

- Start from an existing small quadruped (for example from MuJoCo Menagerie), scaled, to prove the pipeline before a custom hamster MJCF.
- Train stand, walk, turn, stop with domain randomization, then add spine joints in the custom model.
- AMP-style style reward from the keypoint data as an experiment.
- ONNX export and output comparison.
- **Exit:** reproducible benchmark (success rate, falls per episode, speed tracking) across 5 seeds.
- **Kill criterion:** if stable walking isn't achieved within the time box, keep the stand-in quadruped and revisit custom morphology later.

### Phase 5 — Integration: physics to realistic motion (3–4 weeks)

- Swap locomotion into the skill library, build the retargeting layer, trajectory clips for live view.
- Tag all events by origin. Verify clip replay matches the stored seed.
- **Exit:** live view shows the realistic hamster driven by the learned policy, and a reconnect restores state.

### Phase 6 — Hamster-specific behaviours (6–10 weeks)

- One behaviour at a time, each with animation, physics treatment and an A/B check: cheek stuffing, hind-leg standing, wheel, digging, nesting.
- Digging and nesting are the hardest. Treat them as visually authored skills with learned selection and timing until a learned version beats it. Label them honestly in the Observatory.
- **Exit:** at least five behaviours pass a motion-realism check against reference footage.

### Phase 7 — Cognition and ablations (4–6 weeks)

- Add RND curiosity, spatial familiarity, preference estimates.
- Run and publish the autonomy report.
- **Exit:** at least one reproducible, measured behaviour change caused by memory or curiosity.

### Phase 8 — Cinematic moments and polish (4–6 weeks)

- Cycles pipeline that re-renders a logged episode from its seed into a clip, plus audio.
- Full Habitat Studio UI, Brain Observatory, Training Lab, Memory screen, mobile layout.
- **Exit:** a daily "moment" clip is delivered to Telegram automatically.

### Phase 9 — Hardware readiness (optional, later)

- Decide robot scale first (see Section 10), then actuators, then the hardware adapter and safety layer.

**Rough total:** about 8–12 months for a realistic first public version at this pace, with Phase 3 and Phase 6 being the largest uncertainties. Parallel tracks (art, AI, infrastructure) shorten the calendar but not your hours.

## 9. Limitations and mitigations

| Limitation | Impact | Mitigation |
| --- | --- | --- |
| Real-time fur can't match offline quality | Close-ups look CG | Two-tier rendering. Cycles clips for key moments. |
| Browser GPU budgets vary widely | Fur and bedding lag on phones | LOD, quality presets, shell count scaling, performance test on a phone |
| WebGPU and strand fur are still maturing | Risk of dead ends | Prototype early, keep shells plus fins as the fallback |
| Visual realism needs lots of art time | Delays the AI work | Run asset work in parallel, timebox, buy or license base assets only where licensing allows |
| Generic quadruped gait looks wrong | Breaks illusion | Reference-motion style reward plus procedural spine, head, ear, whisker layers |
| Locomotion RL may stall | Blocks everything | Vertical slice on a simple body first, stand-in quadruped, kill criteria |
| CPU MuJoCo is slow for legged RL | Weeks of training | MJX or GPU-parallel tooling, benchmark first |
| RTX 5070 (Blackwell) needs a recent CUDA build | Install failures | Verify CUDA 12.8+ PyTorch before anything else |
| 8 GB VRAM | Limits environments and rendering at once | Separate training, rendering and testing sessions |
| Background life could become rule-based | Undermines "real AI" | Skill-outcome models from real physics episodes, event origin tags |
| Cloud free tiers sleep or throttle | Missed ticks | Lazy catch-up, scheduled ticks, idempotent updates |
| Live physics streaming is costly | Bandwidth and latency | Server-generated trajectory clips replayed client-side |
| Deformable bedding and digging are hard in rigid-body physics | Hard to make real | Simplified physics contact, richer visual deformation, honest labelling |
| Memory could be just a log | Fake cognition | Feed memory features into the policy and prove it with ablations |
| Reward hacking and curiosity traps | Odd behaviours | Log each reward term, novelty decay, behaviour diversity checks |
| Notification fatigue | Parent mutes the bot | Daily digest, rare moments, quiet hours, rate limits |
| Sim-to-real gap | Policy fails on hardware | Randomization, actuator models, independent safety layer, staged tests |
| Hamster-sized robot isn't feasible with off-the-shelf actuators | Hardware plan mismatch | Choose a hamster-*inspired* larger robot, set scale before motor selection |
| Reference footage licensing | Legal risk | Use your own footage or clearly licensed material, record sources |
| Scope explosion | Never ships | One headline claim per phase, time boxes, kill criteria |
| "Indistinguishable" claim can't be proven in all conditions | Overclaiming | Blind A/B tests per tier, report results honestly |

## 10. Hardware path (when you get there)

- A real \~100 g robot with 12 degrees of freedom is not realistic with off-the-shelf actuators. Decide the target: a hamster-*inspired* robot at a larger scale, roughly small hobby quadruped size.
- The shared observation and action contracts, ONNX export, and a safety layer independent of the policy remain as designed in the blueprint.
- Make the physics model's mass, torque limits and actuator dynamics match the intended hardware before final training.
- A physical robot will not look like the photoreal hamster. The photoreal asset belongs to the virtual pet, and the robot is a separate embodiment of the same "brain".

## 11. Budget and licensing checklist

- Free or near-free: Blender, MuJoCo, PyTorch, Three.js, Supabase and Vercel free tiers (verify current limits).
- Possible spend: asset licences, a domain, extra storage for clips, and possibly a cloud GPU for occasional Cycles renders if the laptop is too busy.
- Keep a `THIRD_PARTY_NOTICES.md` and check each repository and asset licence before reuse.
- Set cost alerts before enabling any paid resource.

## 12. Your first 30 days

1. Day 1–2: install PyTorch with CUDA 12.8+, confirm GPU, install MuJoCo and test MJX.
2. Day 3–5: benchmark CPU vs. GPU stepping with a toy quadruped.
3. Day 5–10: collect 2–3 hours of hamster reference video and 100+ photos, organised by behaviour.
4. Week 2: create the repo, contracts, and decision log. Build the simplified-body habitat environment.
5. Week 2–3: implement drives and homeostatic reward, then a three-skill library.
6. Week 3–4: start the Blender hamster sculpt. Run a fur prototype test in Three.js with a placeholder mesh.
7. End of week 4: review. Re-baseline the timeline using the actual hours and measured benchmarks.

## 13. The success definition

HAMMY succeeds if:

- Blind viewers can't reliably tell its Cycles moments from real footage, and most are fooled by the live view at normal distance.
- Its behaviours demonstrably change with memory and curiosity (ablations).
- Its world persists and replays correctly while you are away.
- Every claim in the Observatory points to real recorded data.
