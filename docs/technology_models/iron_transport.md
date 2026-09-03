# Iron Transport Model

The U.S. has developed an infrastructure for transporting iron ore from the northern Minnesota and Michigan iron ranges to ironmaking/steelmaking facilities that takes advantage of barge shipping in the Great Lakes region.
No other significant practical waterway shipping routes exist for the massive amounts of iron ore required for industrial applications in the inland USA, and rail is the only practicable means of transport over long distances otherwise.
Therefore, our transport model was developed to model shipping cost via domestic water transportation through the Great Lakes between selected port cities, and via class 1 rail between all other points.

For the water transportation portion of the model, selected port cities with relevant iron ore infrastructure were selected and waypoints plotted in between to calculate a shipping distance through the Great Lakes.
A [1997 article](https://msaag.aag.org/wp-content/uploads/2013/05/9_Dager.pdf) identified the charged rates for shipping iron ore through the Great Lakes as ranging between \$6.00 and \$7.50 per ton between Duluth/Superior and Lake Erie docks.
Using the midpoint price of \$6.75/ton and the Cleveland docks as a midpoint for Lake Erie, this equates to 0.844 cents per ton-mile in 1997.
Then using the the Bureau of Transportation Statistics' average freight revenue per ton-mile price index for domestic water transportation \cite{BTS}, the price was converted to 2022 prices (the most recent year available in the data).
This gives a final price of 2.35 cents per ton-mile (in 2022 dollars) for Great Lakes barge shipping used in the model.

For rail transportation, no public data was obtainable for iron ore specifically, so the general Class 1 rail transport cost from the [Bureau of Transportation Statistics](https://www.bts.gov/content/average-freight-revenue-ton-mile) was used (5.22 cents per ton-mile in 2022).
Modeling the specific rail routes between mines and iron/steel plant locations was found to be infeasible with available models, so estimates of rail route length were derived from the straight line distances.
This was done using the concept of a [circuity ratio](http://dx.doi.org/10.2139/ssrn.5163676), i.e. the ratio between the straight line distance and the shipping distance through the road/rail network.
While there is extensive data for rail circuity ratio in European countries (with a median of [1.43](http://dx.doi.org/10.2139/ssrn.5163676)), such data could only be found for highway networks in the U.S., not rail.
Therefore, we used the Federal Railroad Administration's recommendation of multiplying the truck shipping distance by a factor of [1.4](https://www.dot.ny.gov/divisions/operating/opdm/passenger-rail/passenger-rail-repository/BCA%20instructions.pdf).
Roads in the continental U.S. have an average circuity factor of [1.20](https://doi.org/10.1016/S0965-8564(01)00044-1) and multiplying this by the FRA recommendation of 1.4 gives the final rail circuity ratio of 1.68 used in the model.
This is unsurprisingly slightly higher than the average European country given the relatively low density of rail networks in the US.

To calculate the final iron ore transport cost, two potential costs are calculated: a rail-only cost and a rail+water cost.
Whichever cost is lower is used as the final transportation cost, with the rail+water cost being generally lower in the Eastern US and the rail-only cost being lower in the West.
