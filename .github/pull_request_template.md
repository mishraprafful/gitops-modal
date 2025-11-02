<!-- markdownlint-disable MD041 -->
## Description

<!-- Provide a clear and concise description of your changes -->

## Type of Change

<!-- Mark the relevant option with an "x" -->

- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📝 Documentation update
- [ ] 🔧 Configuration/Infrastructure change
- [ ] ♻️ Code refactoring (no functional changes)
- [ ] ⚡️ Performance improvement
- [ ] ✅ Test update

## Related Issues

<!-- Link to related issues using keywords: Fixes #123, Closes #456, Relates to #789 -->

Fixes #

## Changes Made

<!-- List the key changes made in this PR -->

-
-
-

## Testing Performed

<!-- Describe the testing you've done -->

### Test Environment

- [ ] kind
- [ ] minikube  
- [ ] GKE
- [ ] EKS
- [ ] AKS
- [ ] Other: ___________

### Test Cases

<!-- Describe specific test cases and their results -->

```bash
# Example test commands you ran
kubectl apply -f examples/...
kubectl get modaldeployments
```

**Test Results:**

- [ ] All existing tests pass
- [ ] New tests added and passing
- [ ] Manual testing completed
- [ ] Tested in multiple environments

## Configuration Changes

<!-- If applicable, provide example configuration showing new/changed fields -->

### Before

```yaml

```

### After

```yaml

```

## Screenshots/Logs

<!-- If applicable, add screenshots or relevant log output -->

```
# Paste relevant logs here
```

## Documentation Updates

- [ ] README.md updated
- [ ] DEVELOPMENT.md updated
- [ ] Code comments added/updated
- [ ] Examples updated/added
- [ ] CRD documentation updated
- [ ] No documentation needed

## Checklist

<!-- Ensure you've completed these items before submitting -->

- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings or errors
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published
- [ ] I have checked my code and corrected any misspellings
- [ ] I have updated the CHANGELOG.md file (if applicable)

## CRD/API Changes

<!-- If you've modified the CRD, fill this out -->

- [ ] CRD schema updated in `crds/modaldeployment-crd.yaml`
- [ ] Backward compatible with existing deployments
- [ ] Migration guide provided (if breaking change)
- [ ] Validation added for new fields

## Deployment Notes

<!-- Special instructions for deploying/testing this change -->

<!-- Example:
- Requires CRD update: `kubectl apply -f crds/modaldeployment-crd.yaml`
- Requires secret update: `kubectl create secret...`
- Breaking change: existing resources need to be updated
-->

## Additional Notes

<!-- Any additional information that reviewers should know -->

---

<!-- Thank you for contributing to gitops-modal! -->
