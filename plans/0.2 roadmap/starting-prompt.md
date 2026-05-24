Ok the basics are very good, now its time to add a new long term plan. I have created the directory "space-game/plans/0.2 roadmap" you should write the new plan document there. You should help me plan and sort these priorities into a full roadmap plan. The priorities we have are:

- Increase collision fidelity, make the ship visual model and collision model match or become more similar, make the player able to stand on top of the ship and other objects
- increase ship detail, open and closing hatch for entry, transparent cockpit which matches the visual model
- increase planet detail - more realistic objects, more textures, more diversity of surface geometry and biome, larger size

How should we break these down into ordered steps for implementation and in which order should we proceed through them? Our goal is to greatly increase visual fidelity, geometry, collision and immersiveness. We will still prioritize using free open source assets, or creating our own, but we should no longer be thinking in terms of quick place holders, we now want to aim for immersive and polished. We should have the human review options for external assets whenever we choose to bring in more of those.

Now write the high level roadmap plan for this.

-----------------------

All of your plans and recommendations generally lean towards taking the smaller incremental step. This might be a good idea, but our goal is to start reaching for the ambitious larger outcomes. For example for exterior ship surfaces being walkable, we want the whole outer surface to seem walkable with some reasonable fidelity to the visual model rather than just 1 or 2 simple surfaces. It is OK to take small incremental steps to get there, but if that is the case then we need to map out the full roadmap towards the more ambitious outcomes too.

Should we further break our 0.2.1 plan down into multiple phases and detail implementation plans for each of those? or should we expand the 0.2 roadmap itself with more detailed steps? Lets discuss this overall planning concept before we change any docs or do any further implementation. What do you think?

-----------------------

OK lets now step back and asses our approach. Our 0.2 roadmap has has collision foundation as 0.2.1 and then ship exterior as 0.2.2. We have seemingly now covered both in 0.2.1 a-f. It seems like the 3 layers of planning docs from roadmap down to implmentation detail are a good pattern and framework, but we need to be careful to have the right breakdown at each level. It seems the top level plan can be a bit larger in ambition and steps, and then the middle and third layer fill in the incremental steps at increasing detail.

Do you have any critiques or adjustments to this approach so far? Should we refactor our 0.2 roadmap a bit to reduce redundancy, and then recheck that our 0.2.1 plan captures the new roadmap phase well, and then we can start working on the detailed implementation plans beneath 0.2.1?