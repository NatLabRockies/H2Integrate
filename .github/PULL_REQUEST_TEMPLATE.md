
<!--
IMPORTANT NOTES

1. Use GH flavored markdown when writing your description:
   https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax

2. If all boxes in the PR Checklist cannot be checked, this PR should be marked as a draft.

3. DO NOT DELETE ANYTHING FROM THIS TEMPLATE. If a section does not apply to you, simply write
   "N/A" in the description.

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

## Section 1: Type of Contribution
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

## Section 2: Draft PR Checklist
<!--Tick these boxes if they are complete, or format them as "[x]" for the markdown to render. -->
<!--Complete when opening a draft PR. -->
- [ ] Open draft PR
- [ ] Describe the feature that will be added
- [ ] Fill out TODO list steps
- [ ] Describe requested feedback from reviewers on draft PR
- [ ] Complete Section 7: New Model Checklist (if applicable)
<!-- Describe the feature in this PR and outline next steps -->
### TODO:
- [ ] Step 1
- [ ] Step 2

### Type of Reviewer Feedback Requested (on Draft PR)
<!-- Outline the feedback that would be helpful from reviewers while it's a draft PR -->
**Structural feedback**:

**Implementation feedback**:

**Other feedback**:

## Section 3: General PR Checklist
<!--Complete when converting draft PR to a merge-ready PR. -->
- [ ] PR description thoroughly describes the new feature, bug fix, etc.
- [ ] Added tests for new functionality or bug fixes
- [ ] Tests pass (If not, and this is expected, please elaborate in the Section 6: Test Results)
- [ ] Documentation
  - [ ] Docstrings are up-to-date
  - [ ] Related `docs/` files are up-to-date, or added when necessary
  - [ ] Documentation has been rebuilt successfully
  - [ ] Examples have been updated (if applicable)
- [ ] `CHANGELOG.md` has been updated to describe the changes made in this PR

## Section 3: Related Issues
<!--If this PR relates to an existing GitHub issue, please link the issue and indicate whether this PR would fully or partially resolve that issue. Please also link any issues that were created due to this PR-->


## Section 4: Impacted Areas of the Software
<!--
Replace the below example with any added or modified files, and briefly describe what has been changed or added, and why. Can exclude CHANGELOG.md, doc pages and supported_models.py.
-->
### Section 4.1: New Files
- `path/to/file.extension`
  - `method1`: What and why something was changed in one sentence or less.

### Section 4.2: Modified Files
- `path/to/file.extension`
  - `method1`: What and why something was changed in one sentence or less.

## Section 5: Additional Supporting Information
<!--Add any other context about the problem here.-->


## Section 6: Test Results, if applicable
<!--
Add the results from unit tests and regression tests here along with justification for any
failing test cases.
-->

## Section 7 (Optional): New Model Checklist
<!-- Complete this section only if you checked "New Model" above -->
- [ ] **Model Structure**:
  - [ ] Follows established naming conventions outlined in `docs/developer_guide/coding_guidelines.md`
  - [ ] Used `attrs` class to define the `Config` to load in attributes for the model
    - [ ] If applicable: inherit from `BaseConfig` or `CostModelBaseConfig`
  - [ ] Added: `initialize()` method, `setup()` method, `compute()` method
    - [ ] If applicable: inherit from `CostModelBaseClass`
- [ ] **Integration**: Model has been properly integrated into H2Integrate
  - [ ] Added to `supported_models.py`
  - [ ] If a new commodity_type is added, update `create_financial_model` in `h2integrate_model.py`
- [ ] **Tests**: Unit tests have been added for the new model
  - [ ] [Pytest-style unit tests](https://realpython.com/pytest-python-testing/)
  - [ ] Unit tests are in a "test" folder within the folder a new model was added to
  - [ ] If applicable add integration tests
- [ ] **Example**: If applicable, a working example demonstrating the new model has been created
  - [ ] Input file comments
  - [ ] Run file comments
  - [ ] Example has been tested and runs successfully in `test_all_examples.py`
- [ ] **Documentation**:
  - [ ] Write docstrings using the [Google style](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html)
  - [ ] Model added to the main models list in `docs/user_guide/model_overview.md`
    - [ ] Model documentation page added to the appropriate `docs/` section
    - [ ] `<model_name>.md` is added to the `_toc.yml`





<!--
__ For NREL use __
Release checklist:
- [ ] Update the version in h2integrate/__init__.py
- [ ] Verify docs builds correctly
- [ ] Create a tag on the main branch in the NREL/H2Integrate repository and push
- [ ] Ensure the Test PyPI build is successful
- [ ] Create a release on the main branch
-->
