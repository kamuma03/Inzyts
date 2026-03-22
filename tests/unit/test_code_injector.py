from src.agents.phase2.code_injector import CodeInjector
from src.models.cells import NotebookCell

class TestCodeInjector:
    def test_inject_safety_net(self):
        """Test safety net injection to prevent string leakage."""
        code_without_safety = """
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
model.fit(X_train, y_train)
"""
        cell = NotebookCell(cell_type='code', source=code_without_safety, metadata={})
        cells_with_safety = CodeInjector.inject_safety_net([cell])

        # Should add safety check
        combined_source = "".join(c.source for c in cells_with_safety)
        assert 'select_dtypes' in combined_source
        assert 'X = X.select_dtypes(include=[np.number, \'bool\'])' in combined_source
