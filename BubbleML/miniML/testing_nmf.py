import matplotlib.pyplot as plt
import numpy as np
from sklearn.decomposition import NMF
from sklearn.datasets import load_digits
from sklearn.preprocessing import MinMaxScaler

# Load dataset and normalize it
digits = load_digits()
X = digits.data
scaler = MinMaxScaler()
X_scaled = scaler.fit_transform(X)

# Apply NNMF
n_components = 10
nnmf = NMF(n_components=n_components, init='random', random_state=42)
X_nnmf = nnmf.fit_transform(X_scaled)

# Get the NNMF components
nmf_components = nnmf.components_

# Plot the NNMF components (one row per component)
plt.figure(figsize=(15, 8))
for i, component in enumerate(nmf_components):
    plt.subplot(2, 5, i + 1)
    plt.imshow(component.reshape(8, 8), cmap='gray')
    plt.title(f'Component {i+1}')
    plt.axis('off')

plt.tight_layout()
plt.show()

# Plot the magnitude of coefficients for the first component
plt.figure(figsize=(8, 4))
plt.bar(np.arange(X.shape[1]), nmf_components[0])
plt.title('NNMF Component 1 Feature Coefficients')
plt.xlabel('Feature Index')
plt.ylabel('Coefficient Magnitude')
plt.show()
