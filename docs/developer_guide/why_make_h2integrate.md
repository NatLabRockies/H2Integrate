# H2Integrate Design Rationale

H2Integrate provides a framework for combining technology models into hybrid-system simulations,
technoeconomic analyses, and optimization studies. Its design emphasizes reusable model interfaces
and explicit connections between technologies.

## Why modularity?

Hybrid systems combine components with different physical behavior, cost assumptions, and operating
constraints. H2Integrate separates these concerns into model roles such as performance, cost,
finance, and control, and connects technologies through defined commodities and transport
components. Users can combine the registered models or add components that follow the framework's
interfaces.

## Why use OpenMDAO as the internal framework for H2Integrate?

H2Integrate uses [NASA's OpenMDAO framework](https://github.com/OpenMDAO/OpenMDAO/) to assemble and
run its models.

OpenMDAO provides:
- a proven framework for complex data-passing within multidisciplinary systems
- automatically-generated visualization tools to help understand models and debug them
- internal units handling and conversion
- built-in nonlinear solvers to resolve model coupling
- built-in optimization and parameter sweep drivers
- multiple existing NLR tools use OpenMDAO, including [WISDEM](https://github.com/NLRWindSystems/WISDEM/) and [WEIS](https://github.com/NLRWindSystems/WEIS), so we can draw from institutional knowledge
- gradient-based optimization and MPI-based parallelization capabilities for applicable studies

However, there are a few downsides to using OpenMDAO:
- an additional layer of code that developers must consider
- longer error stack traces that might seem daunting in the terminal
- potentially increased computational costs depending on problem type and size
- it isn't great at optimizing mixed-integer problems

These benefits support H2Integrate's component-level modeling and optimization goals. Contributors
should still consider OpenMDAO's additional abstraction layer, longer error traces, possible
computational overhead, and limitations with mixed-integer optimization.

## Where should code live?

- Reusable technology models, cost and finance models, and integrations that benefit multiple
	projects belong in the H2Integrate repository.
- Project-specific or proprietary models belong in the project repository. They can be integrated
	by implementing the interfaces expected by H2Integrate.
- For the model interfaces and contribution workflow, see
	[Adding a New Technology](adding_a_new_technology.md).
