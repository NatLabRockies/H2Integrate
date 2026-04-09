# Expected User Knowledge

This section details the recommend user knowledge to use H2Integrate for different purposes.
Depending on your background, you may need to learn more about certain topics to use H2Integrate effectively.
The breadth and depth of that knowledge will depend on if you just want to use H2Integrate to run a few example cases, or if you want to develop new models or contribute to the H2Integrate codebase.

## Recommended background in hybrid energy systems

The modular nature of H2Integrate means that there are a variety of technologies and components that comprise the modeled hybrid energy systems.
At the most basic level, users can use the pre-built models in H2Integrate to simulate a hybrid energy system without any prior knowledge.

One of the main selling points of H2Integrate is the ability to integrate other models and technologies into the platform to assess their performance in a larger hybrid energy system.
However, to do this effectively, users should have a basic understanding of the technologies they are integrating, though they may not need to know much about other technologies.

## Required programming skills

The goal of H2Integrate is to make hybrid energy system design accessible to most users while providing a flexible and powerful platform for advanced users.
The main interface to H2Integrate is through the configuration files, which are written in user-readable [YAML](https://www.redhat.com/en/topics/automation/what-is-yaml).
A good amount of hybrid energy system studies can be done using the pre-built examples packaged within H2Integrate or by modifying their config input files.

For users who want to develop new models or contribute to the H2Integrate codebase, a strong understanding of Python is required.
This includes knowledge of object-oriented programming, data structures, and algorithms.
Users should also be familiar with the [Google style](https://www.sphinx-doc.org/en/master/usage/extensions/example_google.html) for docstrings and the use of type hints for function arguments and return values.

## Familiarity with dependencies

H2Integrate itself is a framework that relies on a number of other tools and libraries to function.
Users should be familiar with the following tools and libraries to use H2Integrate effectively:

- [HOPP](https://github.com/NatLabRockies/HOPP): Used for simulating technologies that produce electricity for other components in H2Integrate
- [PySAM](https://github.com/NatLabRockies/pysam): Provides access to the System Advisor Model (SAM) for performance and financial modeling; underlying tool used for modeling certain generation technologies
- [OpenMDAO](https://openmdao.org/): A framework for multidisciplinary optimization, analysis, and design; used for data-passing, model organization, and optimization
- [Pyomo](http://www.pyomo.org/): A Python-based, open-source optimization modeling language; only useful to understand if you are modifying the dispatch algorithms
- [Pandas](https://pandas.pydata.org/): A data manipulation and analysis library used for handling and analyzing data structures; useful for post-processing results
