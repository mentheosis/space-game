/goal Iterate according to this process. Each iteration, for each of the following 5 topics, make one significant and ambitious change to improve that aspect of the ship interior. Write a doc in the repo called "space-game/plans/0.3 roadmap to AAA/spacehope_to_achieve_<iteration#>.md" and write there what you hoped the next rendering round would achieve for each aspect and why you believed it was ambitious enough to push the project forward at an ambitious rate. Once you have improved all 5 aspects, you may run the render check. At the start of the next iteration, read the previous hope to achieve and add a section about whether you think you succeeded. Then right the next hope to achieve doc. Repeat the whole cyle 10 times.

The render check should be based on a walkthrough with this path: 
- Start at the end of the on ramp facing the ship
- walk slowly to the center of the cargo floor, whil moving the camera in a slow sweeping arc from 90 degrees left until 90 degrees right, and curging up to 90 degrees vertically up along the way.
- then turn around, and walk slowly the up the stair to the cockpit.
- Once you are approaching the cockpit chair, repeat the sweeping arc lookaround from left to top to right.

The 5 aspects to improve eatch iteration are:
1. **Material families**
   - Distinct dark structural metal, lighter wall panels, rubber trim/gaskets, worn floor plates, glass/canopy, seat fabric, emissive indicators.
   - Add various amounts of subtle reflectiveness to metallic surfaces, prevent surfaces from looking flat.

2. **Practical lighting**
   - Replace broad “debug bright” feeling with visible light sources: ramp lights, cargo ceiling strips, small wall indicators, cockpit instrument glow.
   - Every light source must have a direction and not be too globally diffuse
   - the interior space should not be too dark, but not bright either.

3. **Ramp/cargo polish**
   - Add more believable ramp wear, tread contrast, side mechanisms, latch/hinge detail.
   - Improve cargo wall/ceiling detail so it has depth, not just ribs and panels.

4. **Cockpit readability**
   - Clean up seats, consoles, canopy framing, and floor around the two-seat cockpit.
   - Make the cockpit route and pilot view feel intentional, but still early vertical slice, not final AAA.

5. **Evidence update**
   - Keep the current interior contact sheet.
   - Add a material/lighting-focused capture set: ramp close-up, cargo aisle, top landing, cockpit sweep