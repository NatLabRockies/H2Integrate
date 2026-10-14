
<!--
IMPORTANT NOTES

1. Use GH flavored markdown when writing your description:
   https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax

2. Draft PRs should submitted for incomplete PRs if one of the following criteria can be met:
   - Feedback or further discussion is required prior to completion of the contribution
   - If all boxes in the PR Checklist cannot be checked, but feedback is desired prior to completion

3. DO NOT DELETE REQUIRED SECTIONS FROM THIS TEMPLATE. Optional sections may be deleted for PRs that
   are ready for review or you may simply write "N/A" in the description.

4. Code snippets to highlight new, modified, or problematic functionality are highly encouraged,
   though not required. Be sure to use proper code highlighting as demonstrated below.

   ```python
    def a_func():
        return 1

    a = 1
    b = a_func()
    print(a + b)
    ```
-->

<!--The title should clearly define your contribution succinctly.-->
# Add meaningful title here
<!-- Describe your feature here. Please include any code snippets or examples in this section. -->
[Add description of feature here]

<!-- Required -->
## Type of Contribution
<!-- Check all that apply to help reviewers understand your contribution -->
- [ ] Feature Enhancement
  - [ ] Framework
  - [ ] New Model
  - [ ] Updated Model
  - [ ] Tools/Utilities
  - [ ] Other (please describe):
- [ ] Bug Fix
- [ ] Documentation Update
- [ ] CI Changes
- [ ] Other (please describe):


<!-- Optional, required for draft PRs -->
## Draft PR Checklist
<!--Tick these boxes if they are complete, or format them as "[x]" for the markdown to render. -->
<!--Complete when opening a draft PR. -->
- [ ] Open draft PR
- [ ] Describe the feature that will be added
- [ ] Fill out TODO list steps
- [ ] Describe requested feedback from reviewers on draft PR
- [ ] Complete Section 8: New Model Checklist (if applicable)
<!-- Describe the feature in this PR and outline next steps -->

### TODO

- [ ] Step 1
- [ ] Step 2

### Type of Reviewer Feedback Requested (on Draft PR)
<!-- Outline the feedback that would be helpful from reviewers while it's a draft PR -->
**Structural feedback**:

**Implementation feedback**:

**Other feedback**:

<!-- Required, when not a draft -->
## General PR Checklist
<!--Complete when converting draft PR to a merge-ready PR. -->
- [ ] PR description thoroughly describes the new feature, bug fix, etc.
- [ ] New model checklist has been completed (new models only)
- [ ] Tests
  - [ ] All tests pass locally
  - [ ] Added tests for new functionality or bug fixes
  - [ ] Modified tests have been outlined in the impacted areas section
- [ ] Documentation
  - [ ] Docstrings are up-to-date
  - [ ] Related `docs/` files are up-to-date, or added when necessary
  - [ ] Documentation has been rebuilt successfully
  - [ ] Examples have been updated (if applicable)
  - [ ] No changes required
- [ ] `CHANGELOG.md`
  - [ ] At least one complete sentence has been provided to describe the changes made in this PR
  - [ ] After the above, a hyperlink has been provided to the PR using the following format:
    "A complete thought. [PR XYZ]((https://github.com/NatLabRockies/H2Integrate/pull/XYZ)", where
    `XYZ` should be replaced with the actual number.


<!-- Required -->
## Related Issues
<!--
If this PR relates to an existing GitHub issue, please link the issue and indicate whether this PR
would fully or partially resolve that issue. Please also link any issues that were created due to this PR

https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue
-->
[N/A or appropriately link related issues]


<!-- Required -->
## Impacted Areas of the Software
<!--
List new/modified functionality with a one sentence description of what and why something was added/changed.
EXCLUDE: CHANGELOG.md; docs/ files; or batch changes.

Batch changes: do NOT list every individual change when linting, reformatting, or modifying a
common API component, only list the essential changes, but do provide a high level description
for appropriate batch edits.
-->
### New Files
- `path/to/file.extension`
  - `method1`: What and why something was changed in one sentence or less.

### Modified Files
- `path/to/file.extension`
  - `method1`: What and why something was changed in one sentence or less.

<!-- Optional -->
## Additional Supporting Information
<!--Add any other context about the problem here.-->


<!-- Optional -->
## Test Issues
<!--
Add the results from unit tests and regression tests here along with justification for any
failing test cases.
-->

<!-- Optional -->
## New Model Checklist
<!-- Complete this section only if you checked "New Model" above -->
- [ ] **Model Structure**:
  - [ ] Follows established naming conventions outlined in `docs/developer_guide/coding_guidelines.md`
  - [ ] Configuration class is named `{ModelName}Config`, where `{ModelName}` is the complete model class name
  - [ ] Used `attrs` class to define the `Config` to load in attributes for the model
    - [ ] If applicable: inherit from `BaseConfig` or `CostModelBaseConfig`
  - [ ] Added: `initialize()` method, `setup()` method, `compute()` method
    - [ ] If applicable: inherit from `PerformanceModelBaseClass` and `CostModelBaseClass`
- [ ] **Integration**: Model has been properly integrated into H2Integrate
  - [ ] Add the new model to the appropriate `__init__.py` file so it can be imported from its subpackage
  - [ ] Import and apply the register decorator from `h2integrate/core/supported_models.py` to enable H2I to recognize the new model
- [ ] **Tests**: Unit tests have been added for the new model
  - [ ] [Pytest-style unit tests](https://realpython.com/pytest-python-testing/)
  - [ ] Unit tests are in a "test" folder within the folder a new model was added to
  - [ ] If applicable, add integration tests
- [ ] **Example**: If applicable, a working example demonstrating the new model has been created
  - [ ] Input file comments
  - [ ] Run file comments
  - [ ] Example has been tested and runs successfully in `test_all_examples.py`
- [ ] **Documentation**:
  - [ ] Write docstrings using the [Google style](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html)
  - [ ] Model documentation page added to the appropriate `docs/` section
  - [ ] Path to model documentation page is added to the `_toc.yml`

<!-- Optional, release PRs to main, NLR use only -->
## Release checklist

- [ ] Update the version in `h2integrate/__init__.py`
- [ ] Verify docs builds correctly
- [ ] Create a tag on the main branch in the NatLabRockies/H2Integrate repository and push
- [ ] Ensure the Test PyPI build is successful
- [ ] Create a release on the main branch
