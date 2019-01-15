# -*- coding: utf-8 -*-
import dash
import dash_core_components as dcc
import dash_html_components as html
import pandas as pd
import numpy as np
import json
import colorlover as cl
import plotly.graph_objs as go


# Read play-by-play from local csv file
pbp_file = '/home/welced12/googledrive/nfl_data/devl/pfr_parsedplays.csv'
all_pbp = pd.read_csv(pbp_file)


# Define node labels and colors
node_label = {
    0:"1st & 10", 1:"1st & >10", 2:"1st & <10",
    3:"2nd & 1-5", 4:"2nd & 6-10", 5:"2nd & 11+",
    6:"3rd & 1-3", 7:"3rd & 4-7", 8:"3rd & 8+",
    9:"4th Down",
    10:"Punt", 11:"FG Attempt", 12:"Turnover", 13:"End of Half",
    14:"Unknown", 15:"Shenanigans", 16:"First Down/TD"
}

node_goodness = {
    0:50, 1:33, 2:66,
    3:80, 4:50, 5:33,
    6:75, 7:50, 8:25,
    9:33,
    10:10, 11:75, 12:0, 13:50,
    14:50, 15:50, 16:99
}
colorscale = cl.to_rgb(cl.interp( cl.scales['9']['div']['RdYlGn'], 100 ))
cscale = [rgb.replace(')',', 0.5)').replace('rgb','rgba') for rgb in colorscale]
node_color = {n:colorscale[node_goodness[n]] for n in node_goodness}
flow_color = {n:cscale[node_goodness[n]] for n in node_goodness}


# Functions for making dataframes that store info for diagrams
def check_valid_source(play):
    
    # Check for normal down
    if play['down'] not in ['1','2','3','4']:
        return False
    else:
        down = int(play['down'])
        
    # Check play type and result
    if play['is_punt'] or play['is_fieldgoal']:
        return False
    
    dist = int(play['dist'])
    
    # Check for turnover
    if play['is_turnover']:
        return True
        
    # Check for penalty
    if play['is_penalty']:
        return True
    
    else:
        return True
    
def check_valid_target(play):
    
    # Check for end of half, etc.
    oc = str(play['onecell']).lower()
    if ("3rd quarter" in oc) or ("end of " in oc):
        return True
    
    if play['down'] not in ['1','2','3','4']:
        return False
    else:
        down = int(play['down'])
        dist = int(play['dist'])
    
    # Check for punt or FG
    if play['is_punt']:
        return True
    elif play['is_fieldgoal']:
        return True    
    
    return True
    

def get_src_tgts(df):
    # Add column for whether play is a valid target or source
    valid_target = []
    valid_source = []
    for idx in df.index:
        play = df.loc[idx]
        play_dict = play.to_dict()
        valid_source.append(check_valid_source(play_dict))
        valid_target.append(check_valid_target(play_dict))
    df['source'] = valid_source
    df['target'] = valid_target
    return df


def get_node(play_dict):
    down = int(play_dict['down'])
    dist = int(play_dict['dist'])
    # Logic map for determining node number for standard down/dist situations
    if down == 1:
        if dist == 10 or (dist == 50 - play_dict['off_fieldpos']):
            return 0
        elif dist > 10:
            return 1
        elif (dist < 10) and (dist < 50 - play_dict['off_fieldpos']):
            return 2

    elif down == 2:
        if dist < 6:
            return 3
        elif dist <= 10:
            return 4
        elif dist > 10:
            return 5
            
    elif down == 3:
        if dist < 4:
            return 6
        elif dist < 8:
            return 7
        elif dist >= 8:
            return 8
            
    elif down == 4:
        return 9
    
    return 14


def make_sankey_dfs(df, offense='', defense='', verbosity=0):
    # Evaluate whether each play can be a valid source/target for flows
    df = get_src_tgts(df)
    
    idx = df.index
    i = 0; j = 0
    nodes = {k:[] for k in node_label}
    flows = {}
    
    # Iterate through index. Step until we find valid source.
    # Then step from there until we find valid target.
    # Add source to node. Determine if target is terminus.
    # Add flow
    
    while j < len(idx):
#    while j < 50:

        # Step through index until we find a valid source
        src = False
        while i < len(idx) and (not src):
            src = df.loc[idx[i],'source']
            i += 1
        src_row = idx[i-1]
        
        # Step from source until we find a valid target
        j = i
        tgt = False
        while j <= len(idx) and (not tgt):
            tgt = df.loc[idx[j],'target']
            j += 1
        tgt_row = idx[j-1]
        
        # Now we should have source/target pair.
        src_play = df.loc[src_row].to_dict()
        tgt_play = df.loc[tgt_row].to_dict()
        print_cols = ['detail_text','poss','off_fieldpos','down','dist','yds_gained']
        if verbosity > 4:
            print("Source and Target plays:")
            print(df.loc[(src_row,tgt_row),print_cols])
        
        # Add source to proper node
        src_node = get_node( src_play )
        
        ### Look at source play for particular scenarios
        # Check for punt, FG, and turnovers
        if src_play['is_turnover']:
            tgt_node = 12
        elif tgt_play['is_punt']:
            tgt_node = 10
        elif tgt_play['is_fieldgoal']:
            tgt_node = 11
            
        # If source play is a penalty
        elif src_play['is_penalty']:
            print('src_play.off_fieldpos:',src_play['off_fieldpos'])
            print('tgt_play.off_fieldpos:',tgt_play['off_fieldpos'],'dist:',tgt_play['dist'])
            src_1d_yd = int(src_play['off_fieldpos']) + int(src_play['dist'])
            tgt_1d_yd = int(tgt_play['off_fieldpos']) + int(tgt_play['dist'])
            if (int(tgt_play['down']) == 1) and (src_1d_yd != tgt_1d_yd):
                # First down by penalty
                tgt_node = 16
            else:
                tgt_node = get_node( tgt_play )
        
        # If source play is normal offensive play, check for 1st down yardage
        elif src_play['yds_gained'] != 'x':
            
            if int(src_play['yds_gained']) >= int(src_play['dist']):
                tgt_node = 16
            
            # Otherwise, check for down/dist of target play
            elif ("3rd quarter" in str(tgt_play['onecell']).lower()) or ("end of " in str(tgt_play['onecell']).lower()):
                tgt_node = 13
            elif int(tgt_play['down']) in [2,3,4]:
                tgt_node = get_node( tgt_play )
            
        else:
            tgt_node = 15
        
        if verbosity > 4:
            print("Source:",src_node,node_label[src_node])
            print("Target:",tgt_node,node_label[tgt_node])
            print("")
        
        # Add source nodes to dict of nodes
        if src_node not in nodes:
            nodes[src_node] = [src_row]
        elif src_row not in nodes[src_node]:
            nodes[src_node].append(src_row)
        
        # Add terminal nodes to dict of nodes as well
        if tgt_node in ['Punt','FG Attempt','Turnover','End of Half','First Down/TD']:
            if tgt_node not in nodes:
                nodes[tgt_node] = [tgt_row]
            elif tgt_row not in nodes[tgt_node]:
                nodes[tgt_node].append(tgt_row)
                
        # Add flow to dict of flows, excluding acyclic flows
        if node_label[src_node][0] != node_label[tgt_node][0]:
            flow_tuple = (src_node, tgt_node)
            if flow_tuple not in flows:
                flows[ flow_tuple ] = [src_row]
            elif src_row not in flows[ flow_tuple ]:
                flows[ flow_tuple ].append(src_row)
        
        
    # Consolidate nodes and flows dictionaries to proper DataFrames
    if offense == '' and defense == '':
        nodes_df = pd.Series({
            k: len(nodes[k]) for k in nodes
        })
        flows_df = pd.DataFrame(
            [
                [a, b, len(flows[(a,b)])] for (a,b) in flows
            ],
            columns=['Source','Target','Value']
        )
    elif offense != '':
        if verbosity > 0:
            print("Filtering for offense",offense)
        # For each of the nodes, select just the plays for the specified offense
        nodes_df = pd.Series({
            k: sum(
                1 if df.loc[pid,'poss']==offense else 0 for pid in nodes[k]
            ) for k in nodes
        })
        flows_df = pd.DataFrame(
            [
                [
                    a, b, 
                    sum(1 if df.loc[pid,'poss']==offense else 0 for pid in flows[(a,b)])
                ] for (a,b) in flows
            ],
            columns=['Source','Target','Value']
        )
    elif defense != '':
        if verbosity > 0:
            print("Filtering for defense",defense)
        nodes_df = pd.Series({
            k: sum(
                1 if df.loc[pid,'def']==defense else 0 for pid in nodes[k]
            ) for k in nodes
        })
        flows_df = pd.DataFrame(
            [
                [
                    a, b, 
                    sum(1 if df.loc[pid,'def']==defense else 0 for pid in flows[(a,b)])
                ] for (a,b) in flows
            ],
            columns=['Source','Target','Value']
        )
    nodes_df = pd.DataFrame(nodes_df,
                            columns=['Value']).sort_index()
    nodes_df['Label'] = nodes_df.index.map(node_label)
    nodes_df['Color'] = nodes_df.index.map(node_color)
    flows_df['Color'] = flows_df.Target.map(flow_color)
    
    return nodes_df, flows_df


# Function to create a Sankey diagram
def sankey_diagram(nodes_df, flows_df):
    data = dict(
        type='sankey',
        node = dict(
            pad = 15,
            thickness = 20,
            line = dict(
                color = 'black',
                width = 0.5
            ),
            label = nodes_df['Label'],
            color = nodes_df['Color']
        ),
        link = dict(
            source = flows_df['Source'],
            target = flows_df['Target'],
            value = flows_df['Value'],
            color = flows_df['Color'],
            line = dict(
                color = 'black',
                width = 0.25
            )
        ),
        valueformat='i'
    )
    
    layout = dict(
        title = "Game, visualized",
        font = {'size':12}
    )
    
    fig = dict(data=[data], layout=layout)
    return fig


def time_filter( df, season, week_min=1, week_max=17 ):
	time_filter = [
		True if (
			(int(ssn) == season) &
			(int(wk) >= week_min) & (int(wk) <= week_max)
		)
		else False for ( ssn, wk ) in zip(
			df.season.values, df.week.values
		)
	]
	subdf = df[time_filter]
	return subdf

def team_filter( df, offense='', defense='' ):
	if (offense != '' or defense != ''):
		team_filter = [
			True if (
				(home == offense) | (home == defense) |
				(away == offense) | (away == defense)
			)
			else False for ( home, away ) in zip(df.home.values, df.away.values)
		]
		subdf = df[team_filter]
		return subdf
	else:
		return df


## Sample onegame df
#onegame = all_pbp[
#    (all_pbp.season == 2018) &
#    (all_pbp.week == 1) &
#    (all_pbp.home == 'DEN')
#]


external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)


app.layout = html.Div([
	# Radio selector for filtering by offense or defense
	dcc.RadioItems(
		id='dropdown-offdef',
		options=[{'label':i, 'value':i} for i in ['offense','defense']],
		value='offense'
	),
	# Dropdown selector for team name to filter by
	html.Div([
		dcc.Dropdown(
			id='team-name',
			options=[{'label': i, 'value': i} for i in all_pbp['poss'].unique()],
			value='DEN'
		)
	]),
	# Slider for choosing season
	dcc.Slider(
		id='season-slider',
		min=all_pbp.season.min(),
		max=all_pbp.season.max(),
		marks={str(y):str(y) for y in all_pbp.season.unique()},
		value=all_pbp.season.max()
	),
	html.Div([
		dcc.Graph(id='sankey-graphic')
	])
])


@app.callback(
    dash.dependencies.Output('sankey-graphic', 'figure'),
    [dash.dependencies.Input('dropdown-offdef', 'value'),
	dash.dependencies.Input('team-name', 'value'),
	dash.dependencies.Input('season-slider', 'value')]
)
def update_graph(filter_by, teamname, season):

	print("Our parameters are:")
	print("filter_by",filter_by)
	print("teamname",teamname)
	print("season",season)

	# Filter play_by_play by time
	time_filtered_games = time_filter( all_pbp, season, week_min=1, week_max=1 )

	# Filter for games including selected team
	off_tm = teamname if filter_by=='offense' else ''
	def_tm = teamname if filter_by=='defense' else ''
	team_filtered_games = team_filter( all_pbp, offense=off_tm, defense=def_tm )

	if filter_by == 'offense':
		nodes, flows = make_sankey_dfs( team_filtered_games, offense=teamname )
	elif filter_by == 'defense':
		nodes, flows = make_sankey_dfs( team_filtered_games, defense=teamname )
	else:
		print("filter_by:")
		print(filter_by)
	return sankey_diagram(nodes, flows)

if __name__ == '__main__':
    app.run_server(debug=True)
