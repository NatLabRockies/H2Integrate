# Contributing

We welcome contributions in the form of bug reports, bug fixes, improvements to the documentation,
ideas for enhancements (or the enhancements themselves!).

You can find a [list of current issues](https://github.com/NREL/H2Integrate/issues) in the project's
GitHub repo. Feel free to tackle any existing bugs or enhancement ideas by submitting a
[pull request](https://github.com/NREL/H2Integrate/pulls).

## Bug Reports

* Please include a short (but detailed) Python snippet or explanation for reproducing the problem.
  Attach or include a link to any input files that will be needed to reproduce the error.
* Explain the behavior you expected, and how what you got differed.

## Pull Requests

* Please reference relevant GitHub issues in your commit message using `GH123` or `#123`.
* Changes should be [PEP8](http://www.python.org/dev/peps/pep-0008/) compatible.
* Keep style fixes to a separate commit to make your pull request more readable.
* Docstrings are required and should follow the
  [Google style](https://www.sphinx-doc.org/en/master/usage/extensions/example_google.html).
* When you start working on a pull request, start by creating a new branch pointing at the latest
  commit on [main](https://github.com/NREL/H2Integrate).
* Code formatting is enforced using pre-commit hooks and is required for any code pushed up to the repo. The pre-commit package is included in the developer install of the repository. The pre-commit hooks can be installed by running
```bash
pre-commit install
```
in the repository directory. This will automatically run the pre-commit formatting hooks when code changes are committed. If you are having difficulty committing code after it has been reformatted by these hooks, try using the commit command
```bash
git commit -am "<Your commit message here>"
```
which will re-add the reformatted files to the commit.
* The H2Integrate copyright policy is detailed in the [`LICENSE`](https://github.com/NREL/H2Integrate/blob/main/LICENSE).

## Documentation

When contributing new features, or fixing existing capabilities, be sure to add and/or update the
docstrings as needed to ensure the documentation site stays up to date with the latest changes.

To build the documentation locally, the following command can be run in your terminal in the docs
directory of the repository:

```bash
sh build_book.sh
```

In addition to generating the documentation, be sure to check the results by opening the following
path in your browser: `file:///<path-to-h2integrate>/H2Integrate/docs/_build/html/index.html`.

```{note}
If the browser appears to be out of date from what you expected to be built, please try the following, roughly in order:
1. Reload the page a few times
2. Clear your browser's cache and open the page again.
3. Delete the `_build` folder and rebuild the docs
```

## Tests

The test suite can be run using `pytest tests/h2integrate`. Individual test files can be run by specifying them:

```bash
pytest tests/h2integrate/test_hybrid.py
```

and individual tests can be run within those files

```bash
pytest tests/h2integrate/test_hybrid.py::test_h2integrate_system
```

When you push to your fork, or open a PR, your tests will be run against the
[Continuous Integration (CI)](https://github.com/NREL/HOPP/actions) suite. This will start a build
that runs all tests on your branch against multiple Python versions, and will also test
documentation builds.

## Code Review Process

All pull requests will be reviewed by at least one other person before being merged into the develop branch.
Here are some guidelines to help with the review process, both as the person submitting the pull request, and as the reviewer.

### As the person submitting the pull request

- Quality is a priority -- take the time to ensure your code is clear, well-documented, and tested.
- Keep pull requests small enough to be reviewed in under 30 minutes; this helps reviewers give thorough feedback and makes the process more efficient.
- Value readability and understandability, but balance this with computational efficiency. Readable code is preferred unless a more abstract or optimized approach is clearly necessary and well-justified.
- Be open to discussion and feedback. If written communication becomes challenging, consider scheduling a call to clarify intent and resolve misunderstandings.
- Express appreciation for feedback, even if it's critical -- good reviews take time and effort.
- When requesting a review, notify the reviewer directly (e.g., via email or Teams) to ensure timely attention.
- Ask for a review, not just approval. The goal is to improve the codebase together and constructive feedback is an integral part of that process

### As the reviewer

- Test the code locally when possible to verify changes.
- Aim to either accept the pull request or request specific changes, rather than leaving only comments.
- Provide feedback constructively -- focus on the code and its functionality, not the person who wrote it.
- If you leave several critical suggestions, include positive feedback on aspects you appreciate.
- Communicate promptly once the PR author has addressed your feedback; aim to complete reviews within 2-3 days barring extenuating circumstances.
- Remember, communication is key -- maintain a collaborative and respectful tone throughout the process.

```{note}
Code readability and understandability are highly valued, but not at the expense of significant inefficiency. Strive for a balance between clear code and appropriate performance with a slight preference for clear code.
```

## Release Process

### Standard

Most contributions will be into the `develop` branch, and once the threshold for a release has been
met the following steps should be taken to create a new release

1. On `develop`, bump the version appropriately, see the
   [semantic versioning guidelines](https://semver.org/) for details.
2. Open a pull request from `develop` into `main`.
3. When all CI tests pass, and the PR has been approved, merge the PR into main.
4. Pull the latest changes from GitHub into the local copy of the main branch.
5. Tag the latest commit to match the version bump in step 1 (replace "v0.1" in all instances below),
   and push it to the repository.

    ```bash
    git tag -a v0.1 -m "v0.1 release"
    git push --origin v0.1
    ```

6. Check that the
   [Test PyPI GitHub Action](https://github.com/NREL/H2Integrate/actions/workflows/publish_to_test_pypi.yml)
   has run successfully.
   1. If the action failed, identify and fix the issue, then
   2. delete the local and remote tag using the following (replace "v0.1" in all instances just like
      in step 5):

      ```bash
      git tag -d v0.1
      git push --delete origin v0.1
      ```

   3. Start back at step 1.
7. When the Test PyPI Action has successfully run,
   [create a new release](https://github.com/NREL/H2Integrate/releases/new) using the tag created in
   step 5.

### Patches

Any pull requests directly into the main branch that alter the H2Integrate model (excludes anything
in `docs/`, or outside of `h2integrate/` and `tests/`), should be sure to follow the instructions
below:

1. All CI tests pass and the patch version has been bumped according to the
   [semantic versioning guidelines](https://semver.org/).
2. Follow steps 4 through 7 above.
3. Merge the NREL main branch back into the develop branch and push the changes.
