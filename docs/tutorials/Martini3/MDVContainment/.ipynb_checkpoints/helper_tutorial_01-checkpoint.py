# These are the helper functions for tutorial 1
import mdvcontainment.composition_logic as cl
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
try:
    import ipywidgets as widgets
    from IPython.display import display
    import plotly.graph_objs as go
except:
    print('Pywidgets not in current environment, advanced plotting will not work. ($pip install pywidgets).')

def analyse_composition(u, containment, compositions, mode='names', savefig='compositions.png',
                        dpi=300, show=True, min_label_percent=5, max_display_items=9):
    """
    Plots pie charts of component compositions with consistent legends.

    - Shows only top `max_display_items` components in pie and groups the rest as 'Other'.
    """
    # Get compositions
    nodes = containment.voxel_containment.nodes

    unique_labels = sorted(cl.get_unique_labels(u, mode=mode))
    color_map = cl.get_color_mapping(unique_labels)
    color_map["Other"] = "#cccccc"  # gray for 'Other'

    num_components = len(compositions)
    ncols = int(np.ceil(np.sqrt(num_components)))
    nrows = int(np.ceil(num_components / ncols))
    scale = 4
    figsize = (ncols * scale, nrows * scale)

    fig, axs = plt.subplots(nrows, ncols, figsize=figsize, constrained_layout=True)
    axs = axs.flatten()

    all_keys = list(compositions.keys())
    root_nodes = containment.voxel_containment.root_nodes
    leaf_nodes = containment.voxel_containment.leaf_nodes

    for idx in range(nrows * ncols):
        if idx >= len(all_keys):
            fig.delaxes(axs[idx])
            continue

        ax = axs[idx]
        key = all_keys[idx]
        composition = compositions[key]

        # Sort and split top N and rest
        sorted_items = sorted(composition.items(), key=lambda x: -x[1])
        top_items = sorted_items[:max_display_items]
        other_items = sorted_items[max_display_items:]

        top_dict = dict(top_items)
        if other_items:
            other_total = sum(v for _, v in other_items)
            if other_total > 0:
                top_dict["Other"] = other_total

        # Normalize to percentages
        total = sum(top_dict.values())
        top_percentages = {k: (v / total) * 100 for k, v in top_dict.items()}

        # Filter by min percent (only affects labels, not slices)
        labels = [k if pct >= min_label_percent else '' for k, pct in top_percentages.items()]
        sizes = list(top_percentages.values())
        colors = [color_map.get(k, "#000000") for k in top_percentages.keys()]

        wedges, texts = ax.pie(sizes, labels=labels, colors=colors, startangle=90)

        # Title
        if key in root_nodes and key in leaf_nodes:
            ax.set_title(f'Comp. {key} (root+leaf)')
        elif key in root_nodes:
            ax.set_title(f'Comp. {key} (root)')
        elif key in leaf_nodes:
            ax.set_title(f'Comp. {key} < Comp. {int(containment.voxel_containment.get_parent_nodes([key])[0])} (leaf)')
        else:
            ax.set_title(f'Comp. {key} < Comp. {int(containment.voxel_containment.get_parent_nodes([key])[0])}') 

        # Legend below
        legend_ax = ax.inset_axes([0, -0.3, 1, 0.25])
        legend_ax.axis('off')

        patches = [mpatches.Patch(color=color_map[k], label=f"{k} ({top_percentages[k]:.1f}%)")
                   for k in top_percentages]
        legend_ax.legend(handles=patches, loc='center', ncol=2, fontsize='small',
                         frameon=False, handlelength=1, handletextpad=0.5, columnspacing=1)

    if savefig:
        plt.savefig(savefig, dpi=dpi, bbox_inches='tight')
    if show:
        plt.show()

    return compositions, fig, axs

def show_containment_with_composition(u, containment, compositions, 
                                      mode='names',
                                      label_value_map=None,
                                      cmap_colors=((0.2, 0.2, 0.1), (0.9, 0.9, 0.8)),
                                      max_display_items=9,
                                      min_label_percent=2,
                                      average_other=False,
                                      sort_by_label_values=False):
    """
    Interactive containment DAG with horizontal composition bars using Plotly and ipywidgets.
    Adds depth-based indentation to show DAG hierarchy more clearly.
    Enhanced hover functionality for better interaction.
    Now includes a unified legend at the bottom.
    """
    assert mode in ['names', 'resnames', 'molar'], 'Please specify a valid \'mode\' (\'names\', \'resnames\' or \'molar\')'

    # ----------- Utilities -----------
    def map_labels_to_gradient(label_value_map, cmap_colors, other_color="#cccccc"):
        labels = list(label_value_map.keys())
        values = np.array([label_value_map[label] for label in labels], dtype=float)
        if np.all(values == values[0]):
            norm = lambda x: 0.5
        else:
            norm_obj = mcolors.Normalize(vmin=np.min(values), vmax=np.max(values))
            norm = norm_obj
        cmap = mcolors.LinearSegmentedColormap.from_list("custom_heatmap", cmap_colors)
        label_color_map = {label: cmap(norm(value)) for label, value in label_value_map.items()}
        label_color_map["Other"] = mcolors.to_rgba(other_color)
        return label_color_map

    def average_value(weighted_items, value_map):
        total = sum(weighted_items.values())
        if total == 0:
            return 0.0
        return sum(value_map.get(k, 0.0) * v for k, v in weighted_items.items()) / total

    def average_hex_color(weighted_items, cmap):
        total = sum(weighted_items.values())
        if total == 0:
            return "#cccccc"
        avg_rgb = np.zeros(3)
        for label, weight in weighted_items.items():
            rgb = np.array(mcolors.to_rgb(cmap.get(label, "#000000")))
            avg_rgb += (weight / total) * rgb
        return mcolors.to_hex(avg_rgb)

    # ----------- Color Mapping -----------
    if label_value_map:
        base_color_map = map_labels_to_gradient(label_value_map, cmap_colors)
    else:
        import matplotlib.pyplot as plt
        unique_labels = sorted({k for comp in compositions.values() for k in comp.keys()})
        cmap = plt.get_cmap('tab20', len(unique_labels))
        base_color_map = {label: cmap(i) for i, label in enumerate(unique_labels)}
        base_color_map["Other"] = "#cccccc"

    # Collect all unique labels that appear in the data
    all_labels = set()
    for composition in compositions.values():
        all_labels.update(composition.keys())
    
    # Track if "Other" category will be used
    other_used = False

    # ----------- DAG Traversal -----------
    def traverse_tree(node, depth=0):
        nonlocal other_used
        children = containment.get_child_nodes([node])
        node_box = widgets.HBox()

        # ---- Composition Data ----
        composition = compositions.get(node, {})
        total = sum(composition.values())
        if total == 0:
            composition = {}
            total = 1

        sorted_items = sorted(composition.items(), key=lambda x: -x[1])
        top_items = sorted_items[:max_display_items]
        other_items = sorted_items[max_display_items:]

        top_dict = dict(top_items)
        other_dict = dict(other_items)
        
        # Handle "Other" category - simplified without detailed breakdown
        if other_items:
            other_used = True  # Mark that "Other" is being used
            other_total = sum(v for _, v in other_items)
            if other_total > 0:
                top_dict["Other"] = other_total
                if label_value_map and sort_by_label_values:
                    label_value_map["Other"] = average_value(other_dict, label_value_map)
                if average_other:
                    base_color_map["Other"] = average_hex_color(other_dict, base_color_map)
                else:
                    base_color_map["Other"] = "#cccccc"

        # Sort based on value or percent
        def get_sort_key(label):
            if sort_by_label_values and label_value_map:
                return label_value_map.get(label, -np.inf)
            return -top_dict[label]

        sorted_keys = sorted(top_dict.keys(), key=get_sort_key, reverse=False)
        sizes = np.array([top_dict[k] for k in sorted_keys])
        percents = (sizes / total) * 100
        labels = sorted_keys

        colors = [f'rgba{tuple(int(c*255) for c in mcolors.to_rgba(base_color_map.get(l, "#000")))}' for l in labels]
        
        # Create hover text - same format for all items including "Other"
        hovertext = []
        for i, l in enumerate(labels):
            if mode in ['names', 'resnames']:
                base_text = f"{l}: {sizes[i]} atoms ({percents[i]:.1f}%)"
            elif mode == 'molar':
                base_text = f"{l}: {sizes[i]} unique residues ({percents[i]:.1f}%)"
            if label_value_map and l in label_value_map:
                base_text += f", value: {label_value_map[l]:.2f}"
            
            hovertext.append(base_text)

        # Create individual bar segments for reliable hover detection
        x_positions = np.cumsum([0] + list(percents[:-1]))
        
        traces = []
        for i, (label, percent, color, hover) in enumerate(zip(labels, percents, colors, hovertext)):
            trace = go.Bar(
                x=[percent],
                y=[f'node_{node}'],
                base=[x_positions[i]],
                orientation='h',
                marker=dict(color=color, line=dict(width=0)),
                hoverinfo='text',
                hovertext=hover,
                name=label,
                showlegend=False,
                width=0.8  # Make bars thicker for better hover detection
            )
            traces.append(trace)

        fig = go.FigureWidget(traces)
        fig.update_layout(
            margin=dict(l=0, r=0, t=5, b=5),
            height=53,  # Increased from 35 to ~53 (1.5x)
            width=600,  # Increased from 300 to 600 (2x)
            xaxis=dict(
                visible=False,
                range=[0, 100],
                fixedrange=True
            ),
            yaxis=dict(
                visible=False,
                fixedrange=True
            ),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            hoverlabel=dict(
                bgcolor="white",
                bordercolor="black",
                font_size=16,  # Increased from 12 to 16
                font_family="Arial",
                namelength=-1,  # Show full text without truncation
                align="left"    # Left-align text for better readability
            ),
            barmode='stack',
            hovermode='closest'
        )
        
        # Disable the toolbar and configure hover properly
        config = {
            'displayModeBar': False,
            'staticPlot': False,
            'responsive': True,
            'scrollZoom': False,
            'doubleClick': False,
            'showTips': False,
            'displaylogo': False
        }
        fig._config = config

        total_nvoxels = np.prod(np.array(containment.grid.shape))
        # Label with depth-based indentation
        title = f"<b>Comp. {node}</b> &nbsp;&nbsp;<span style='color:gray'>[{(containment.get_total_voxel_count([node])/total_nvoxels) * 100:.02f} vol%] [rank {containment.component_ranks[node]}]</span>"
        label_html = widgets.HTML(
            value=title,
            layout=widgets.Layout(width="250px", margin=f"0 0 0 {depth * 20}px")
        )

        node_box.children = [label_html, fig]
        node_box.layout = widgets.Layout(align_items='center')  # Center align the box contents

        # Recursively process children
        child_boxes = [traverse_tree(child, depth=depth + 1) for child in children]
        return widgets.VBox([node_box] + child_boxes)

    # ----------- Create Legend -----------
    def create_legend():
        # Determine which labels to include in legend
        legend_labels = list(all_labels)
        if other_used:
            legend_labels.append("Other")
        
        # Sort legend labels
        if sort_by_label_values and label_value_map:
            legend_labels = sorted([l for l in legend_labels if l in label_value_map], 
                                 key=lambda x: label_value_map[x], reverse=True)
            # Add any labels not in label_value_map at the end
            legend_labels.extend([l for l in all_labels if l not in label_value_map])
            if other_used and "Other" not in label_value_map:
                legend_labels.append("Other")
        else:
            legend_labels = sorted(legend_labels)

        # Calculate grid layout - aim for roughly 4-6 columns
        n_labels = len(legend_labels)
        n_cols = min(6, max(3, int(np.ceil(np.sqrt(n_labels * 1.5)))))
        n_rows = int(np.ceil(n_labels / n_cols))
        
        # Create legend items as HTML
        legend_items = []
        for i, label in enumerate(legend_labels):
            color = base_color_map.get(label, "#000000")
            color_hex = mcolors.to_hex(color)
            
            # Create hover title text
            title_text = label
            if label_value_map and label in label_value_map:
                title_text += f" (value: {label_value_map[label]:.2f})"
            
            # Create individual legend item
            legend_item = widgets.HTML(
                value=f"""
                <div style="display: flex; align-items: center; margin: 5px 10px; white-space: nowrap;" title="{title_text}">
                    <div style="width: 20px; height: 15px; background-color: {color_hex}; 
                                margin-right: 8px; border: 1px solid #ccc; flex-shrink: 0;"></div>
                    <span style="font-size: 12px; font-family: Arial; color: #333;">{label}</span>
                </div>
                """,
                layout=widgets.Layout(
                    width=f"{100//n_cols}%",
                    margin="0px"
                )
            )
            legend_items.append(legend_item)
        
        # Arrange items in rows
        legend_rows = []
        for row in range(n_rows):
            start_idx = row * n_cols
            end_idx = min(start_idx + n_cols, len(legend_items))
            row_items = legend_items[start_idx:end_idx]
            
            # Pad row with empty widgets if necessary
            while len(row_items) < n_cols:
                row_items.append(widgets.HTML(value="", layout=widgets.Layout(width=f"{100//n_cols}%")))
            
            legend_row = widgets.HBox(
                row_items,
                layout=widgets.Layout(
                    width="100%",
                    justify_content="flex-start",
                    align_items="center"
                )
            )
            legend_rows.append(legend_row)
        
        # Create title
        title_widget = widgets.HTML(
            value="<div style='text-align: center; font-weight: bold; font-size: 16px; margin-bottom: 10px; font-family: Arial;'>Legend</div>",
            layout=widgets.Layout(width="100%")
        )
        
        # Combine title and legend grid
        legend_widget = widgets.VBox(
            [title_widget] + legend_rows,
            layout=widgets.Layout(
                width="100%",
                padding="15px",
                border="1px solid #ddd",
                background_color="#f8f8f8"
            )
        )
        
        return legend_widget

    # ----------- Assemble Full Tree with Legend -----------
    tree_widgets = [traverse_tree(root, depth=0) for root in containment.root_nodes]
    
    # Create the legend
    legend_widget = create_legend()
    
    # Create a separator
    separator = widgets.HTML(
        value="<hr style='margin: 20px 0; border: 1px solid #ddd;'>",
        layout=widgets.Layout(width="100%")
    )
    
    # Combine everything
    all_widgets = tree_widgets + [separator, legend_widget]
    display(widgets.VBox(all_widgets))