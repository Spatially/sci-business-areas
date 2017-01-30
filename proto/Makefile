export MSA_BASE:=/Users/jbcollins/msa
export MSA_NAME:=proto


all: \
	biz/biz_list.psv \
	biz/site_list.psv \
	biz/site_road_info.psv \
	biz/site_road_distances.psv \
	biz/site_road_distances_scaled.psv \
	roads/road_network.xml \
	areas/ba_site_list.psv \
	areas/ba_site_attributes.psv \
	areas/ba_site_distances.psv \
	areas/ba_site_labels.psv 


roads: roads/road_network.xml


biz_clear:
	rm -f biz/biz_list.psv 
	rm -f biz/biz_site_lookup.psv 
	rm -f biz/site_list.psv 
	rm -f biz/site_density.psv 
	rm -f biz/site_road_info.psv 
	rm -f biz/site_road_distances.psv 
	rm -f biz/site_road_distances_scaled.psv 
	rm -f biz/site_road_remap.* 
	rm -f biz/site_rtree.* 
	rm -f biz/s_relocation.* 
	rm -f biz/s_site_density.* 


areas_clear:
	rm -f areas/ba_clusters.psv
	rm -f areas/ba_merges.psv
	rm -f areas/ba_site_distances.psv
	rm -f areas/ba_site_attributes.psv
	rm -f areas/ba_site_list.psv
	rm -f areas/ba_test_points.psv
	rm -f areas/s_ba_blobs.*
	rm -f areas/s_ba_clusters.*
	rm -f areas/s_ba_ortho.*
	rm -f areas/s_ba_shapes.*
	rm -f areas/s_ba_site_attributes.*
	rm -f areas/s_tri_nodes.*
	rm -f areas/s_tri_edges.*


roads_clear:
	rm -f roads/road_network.xml
	rm -f roads/road_network_edges.*
	rm -f roads/road_network_vertices.*
	rm -f roads/road_edges.psv
	rm -f roads/road_segments.*
	rm -f roads/z_run_osm_queries.sh
	rm -f roads/osm_check
	


#
# Targets related to business and site lists
#
biz/biz_list.psv: biz/biz_list_0.psv
	eero prep_biz_list

biz/site_list.psv: biz/biz_list.psv
	eero get_site_list

biz/site_road_info.psv: biz/site_list.psv roads/road_network.xml
	eero map_sites_to_roads
	
biz/site_road_distances.psv: biz/site_road_info.psv roads/road_network.xml
	eero get_site_road_distances

biz/site_road_distances_scaled.psv: biz/site_road_distances.psv
	eero get_site_road_distances_scaled


#
# Targets related to business areas
#
areas/ba_site_list.psv: biz/biz_site_lookup.psv biz/biz_list.psv
	eero get_ba_site_list

areas/ba_site_attributes.psv: areas/ba_site_list.psv biz/site_road_distances.psv biz/biz_list.psv 
	eero get_ba_site_attributes

areas/ba_site_distances.psv: biz/site_road_distances_scaled.psv areas/ba_site_list.psv
	eero get_ba_site_distances
	
areas/ba_site_labels.psv: biz/site_road_distances_scaled.psv areas/ba_site_list.psv areas/ba_site_attributes.psv areas/ba_parameters.psv
	eero cluster_sites
	eero wrap_clusters
	eero tidy_clusters


#
# Targets related to road networks
#
roads/road_network.xml: roads/osm_check
	eero make_road_network
	eero make_road_shapefiles

roads/osm_check:
	rm -f roads/osm_check
	eero make_osm_road_queries
	cd roads; sh z_run_osm_queries.sh
	cd roads; touch osm_check


