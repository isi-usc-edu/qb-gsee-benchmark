
load("correlation_of_features_and_runtimes.mat");

T = DMRGcomputetimeforhomogeneouscatalysisinstancesS1;


removed_columns = { ... 
    'ProblemInstanceShortName', ...
    'MoleculeName', ...
    'TaskUUID', ...
    'FCIDUMPFileName', ...
    'DMRGUUID', ...
    'CalcUUID'
};

for idx = 1 : length(removed_columns)
    column_to_remove = removed_columns{idx};
    T(:, {column_to_remove}) = [];
end

A = table2array(T);

A_normalized = (A - mean(A,1)) ./ std(A, 0,1);

R = corr(A_normalized);


fig = figure(222);
fig.set('WindowState', 'maximized');
imagesc(R);

varNames = T.Properties.VariableNames;

set(gca, 'TickLabelInterpreter', 'none');

set(gca, 'XTick', 1:numel(varNames), 'XTickLabel', varNames,  ...
         'YTick', 1:numel(varNames), 'YTickLabel', varNames);

xtickangle(45);

title('Correlation Matrix');



% Custom colormap
nColors = 256;
breaks = [-1, -0.8, 0, 0.8, 1];
colors = [
    0.5 0   0; % dark red
    1   0.9 0.9; % light red
    1   0.6 0.6; 
    0.9 0.9 1; % light blue
    0   0   0.5 % dark blue
];
x = linspace(-1, 1, nColors)';
cmap = zeros(nColors, 3);
for i = 1:3
    cmap(:,i) = interp1(breaks, colors(:,i), x, 'linear');
end
cmap = max(0, min(1, cmap));

colormap(cmap);
colorbar;
caxis([-1 1]);

saveas(fig, 'correlation_of_features_and_runtimes.png');



