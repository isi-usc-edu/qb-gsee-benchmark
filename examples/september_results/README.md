# Homogeneous catalysis resource estimates

This directory contains the quantum resource estimates for the homogeneous catalysis paper.
There is one JSON file for each nitrogen fixation application instance.
(Note that for the purposes of these resource estimates, the two reactions for the molydenum pincer (as well as the two active spaces for each reaction) are combined into a single application instace.

Note that the JSON files have a slightly different schema from that defined in QB-Estimate-Reporting.
Key differences are:
* A new property, `tasks`, has been added to reflect the fact that the application instance may contain multiple circuits.
* Properties such as `repetitions`, `logical-abstract`, and `physical` have been moved into the `tasks` array.
* Physical estimates do not include T gate counts or T factory counts because our architecture instead uses AutoCCZ factories to directly implement Toffoli gates.

For more information, see the [homogeneous catalysis overleaf](https://www.overleaf.com/3193359518gxcskngsbbkg#ad0e67) as well as the [basecamp thread about schemas](https://3.basecamp.com/3613864/buckets/26823103/messages/7369217507).
