// Ground of the chunk: grass everywhere, blended with paths, forest floor, dirt and asphalt
// from the real land-use masks (data/splat.png). Layers tile every 4 m; a second, larger
// sample of the grass breaks up the repetition.
shader_type spatial;
render_mode cull_back;

uniform sampler2D splat : filter_linear, repeat_disable;
uniform sampler2D macro : filter_linear, repeat_disable;
uniform sampler2D grass_albedo : source_color, filter_linear_mipmap_anisotropic;
uniform sampler2D grass_normal : hint_normal, filter_linear_mipmap_anisotropic;
uniform sampler2D path_albedo : source_color, filter_linear_mipmap_anisotropic;
uniform sampler2D path_normal : hint_normal, filter_linear_mipmap_anisotropic;
uniform sampler2D forest_albedo : source_color, filter_linear_mipmap_anisotropic;
uniform sampler2D forest_normal : hint_normal, filter_linear_mipmap_anisotropic;
uniform sampler2D dirt_albedo : source_color, filter_linear_mipmap_anisotropic;
uniform sampler2D dirt_normal : hint_normal, filter_linear_mipmap_anisotropic;
uniform sampler2D asphalt_albedo : source_color, filter_linear_mipmap_anisotropic;
uniform sampler2D asphalt_normal : hint_normal, filter_linear_mipmap_anisotropic;
uniform float tile_m = 4.0;
uniform float chunk_size = 640.0;

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

vec4 sharpen(vec4 w, float noise) {
	// crisper borders between layers than the blurred mask gives on its own
	return clamp((w - 0.5 + noise * 0.25) * 2.2 + 0.5, 0.0, 1.0);
}

void fragment() {
	vec2 uv = world_pos.xz / tile_m;
	vec2 suv = (world_pos.xz + chunk_size * 0.5) / chunk_size;
	vec3 g1 = texture(grass_albedo, uv).rgb;
	vec3 g2 = texture(grass_albedo, uv * 0.23 + 0.37).rgb;
	float n = g2.g - 0.35;
	vec4 w = sharpen(texture(splat, suv), n);

	vec3 col = mix(g1, g2, 0.35);
	vec3 nrm = texture(grass_normal, uv).rgb;
	float rough = 0.95;
	col = mix(col, texture(forest_albedo, uv).rgb, w.g);
	nrm = mix(nrm, texture(forest_normal, uv).rgb, w.g);
	col = mix(col, texture(dirt_albedo, uv).rgb, w.b);
	nrm = mix(nrm, texture(dirt_normal, uv).rgb, w.b);
	col = mix(col, texture(path_albedo, uv).rgb, w.r);
	nrm = mix(nrm, texture(path_normal, uv).rgb, w.r);
	rough = mix(rough, 0.85, w.r);
	col = mix(col, texture(asphalt_albedo, uv).rgb, w.a);
	nrm = mix(nrm, texture(asphalt_normal, uv).rgb, w.a);
	rough = mix(rough, 0.8, w.a);

	ALBEDO = col * texture(macro, suv).rgb * 1.25;
	NORMAL_MAP = nrm;
	ROUGHNESS = rough;
	SPECULAR = 0.3;
}
