#define _GNU_SOURCE
#include <assert.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <wayland-client.h>
#include "xdg-shell.h"
#include "text-input.h"
#include "input-method.h"

/* Native canvas prototype: acts as a text-input client and its input method.
 * Run only on a disposable nested compositor (one IM is allowed per seat).
 * stdin: rect x y h | draw w h card-x card-y | offset x y
 *        child w h surface-x surface-y card-x card-y | quit
 */
static struct wl_display *display;
static struct wl_compositor *compositor;
static struct wl_shm *shm;
static struct wl_subcompositor *subcompositor;
static struct wl_seat *seat;
static struct xdg_wm_base *wm;
static struct zwp_text_input_manager_v3 *tm;
static struct zwp_input_method_manager_v2 *im_mgr;
static struct zwp_text_input_v3 *ti;
static struct zwp_input_method_v2 *im;
static struct wl_surface *app_surface, *popup_surface;
static struct zwp_input_popup_surface_v2 *popup;
static struct wl_surface *child_surface;
static struct wl_subsurface *child_role;
static int app_w=800, app_h=600, rx=150, ry=150, rh=24;

static struct wl_buffer *buffer(int w, int h, int cx, int cy, int application) {
    assert(w>0 && h>0 && w<=4096 && h<=4096);
    int fd=memfd_create("popup-canvas-probe", MFD_CLOEXEC);
    assert(fd>=0 && ftruncate(fd, (off_t)w*h*4)==0);
    uint32_t *p=mmap(NULL, (size_t)w*h*4, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0);
    assert(p!=MAP_FAILED);
    for (int y=0; y<h; ++y) for (int x=0; x<w; ++x)
        p[y*w+x]=application ? 0xff202020 :
            (x>=cx && x<cx+120 && y>=cy && y<cy+48 ? 0xffff2400 : 0);
    struct wl_shm_pool *pool=wl_shm_create_pool(shm, fd, w*h*4);
    struct wl_buffer *b=wl_shm_pool_create_buffer(pool, 0, w, h, w*4, WL_SHM_FORMAT_ARGB8888);
    wl_shm_pool_destroy(pool);
    munmap(p,(size_t)w*h*4);
    close(fd);
    return b; // The short-lived probe retains buffers until disconnect.
}
static void draw(int w,int h,int x,int y) {
    wl_surface_attach(popup_surface,buffer(w,h,x,y,0),0,0);
    wl_surface_damage(popup_surface,0,0,w,h);
    struct wl_region *region=wl_compositor_create_region(compositor);
    wl_region_add(region,x,y,120,48);
    wl_surface_set_input_region(popup_surface,region);
    wl_region_destroy(region);
    wl_surface_commit(popup_surface);
    wl_display_roundtrip(display);
    printf("DRAW %d %d %d %d\n",w,h,x,y); fflush(stdout);
}
static void child(int w,int h,int sx,int sy,int cx,int cy) {
    if (!child_surface) {
        assert(subcompositor);
        child_surface=wl_compositor_create_surface(compositor);
        child_role=wl_subcompositor_get_subsurface(subcompositor,child_surface,popup_surface);
        wl_subsurface_set_sync(child_role);
    }
    wl_subsurface_set_position(child_role,sx,sy);
    wl_surface_attach(child_surface,buffer(w,h,cx,cy,0),0,0);
    wl_surface_damage(child_surface,0,0,w,h);
    struct wl_region *region=wl_compositor_create_region(compositor);
    wl_region_add(region,cx,cy,120,48);
    wl_surface_set_input_region(child_surface,region);
    wl_region_destroy(region);
    wl_surface_commit(child_surface);
    wl_surface_attach(popup_surface,buffer(1,1,200,200,0),0,0);
    region=wl_compositor_create_region(compositor);
    wl_surface_set_input_region(popup_surface,region);
    wl_region_destroy(region);
    wl_surface_damage(popup_surface,0,0,1,1);
    wl_surface_commit(popup_surface);
    wl_display_roundtrip(display);
    printf("CHILD %d %d %d %d %d %d\n",w,h,sx,sy,cx,cy);fflush(stdout);
}
static void rect(void) {
    zwp_text_input_v3_set_cursor_rectangle(ti,rx,ry,1,rh);
    zwp_text_input_v3_commit(ti);
}
static void ti_enter(void *d,struct zwp_text_input_v3 *t,struct wl_surface *s) {
    (void)d;(void)s;
    zwp_text_input_v3_enable(t);
    zwp_text_input_v3_set_surrounding_text(t,"",0,0);
    rect();
}
static void ti_leave(void*d,struct zwp_text_input_v3*t,struct wl_surface*s){(void)d;(void)t;(void)s;}
static void ti_preedit(void*d,struct zwp_text_input_v3*t,const char*s,int32_t b,int32_t e){(void)d;(void)t;(void)s;(void)b;(void)e;}
static void ti_commit(void*d,struct zwp_text_input_v3*t,const char*s){(void)d;(void)t;(void)s;}
static void ti_delete(void*d,struct zwp_text_input_v3*t,uint32_t b,uint32_t a){(void)d;(void)t;(void)b;(void)a;}
static void ti_done(void*d,struct zwp_text_input_v3*t,uint32_t s){(void)d;(void)t;(void)s;}
static const struct zwp_text_input_v3_listener ti_listener={
    .enter=ti_enter,.leave=ti_leave,.preedit_string=ti_preedit,
    .commit_string=ti_commit,.delete_surrounding_text=ti_delete,.done=ti_done
};
static void im_activate(void*d,struct zwp_input_method_v2*t){(void)d;(void)t;puts("ACTIVE");fflush(stdout);}
static void im_deactivate(void*d,struct zwp_input_method_v2*t){(void)d;(void)t;}
static void im_surround(void*d,struct zwp_input_method_v2*t,const char*s,uint32_t c,uint32_t a){(void)d;(void)t;(void)s;(void)c;(void)a;}
static void im_change(void*d,struct zwp_input_method_v2*t,uint32_t c){(void)d;(void)t;(void)c;}
static void im_content(void*d,struct zwp_input_method_v2*t,uint32_t h,uint32_t p){(void)d;(void)t;(void)h;(void)p;}
static void im_done(void*d,struct zwp_input_method_v2*t){(void)d;(void)t;}
static void im_unavailable(void*d,struct zwp_input_method_v2*t){(void)d;(void)t;fputs("IM unavailable: do not run on main desktop\n",stderr);exit(2);}
static const struct zwp_input_method_v2_listener im_listener={im_activate,im_deactivate,im_surround,im_change,im_content,im_done,im_unavailable};
static void popup_rect(void*d,struct zwp_input_popup_surface_v2*p,int32_t x,int32_t y,int32_t w,int32_t h){
    (void)d;(void)p;printf("RECT %d %d %d %d\n",x,y,w,h);fflush(stdout);
}
static const struct zwp_input_popup_surface_v2_listener popup_listener={popup_rect};
static void wm_ping(void*d,struct xdg_wm_base*w,uint32_t s){(void)d;xdg_wm_base_pong(w,s);}
static const struct xdg_wm_base_listener wm_listener={wm_ping};
static void top_configure(void*d,struct xdg_toplevel*t,int32_t w,int32_t h,struct wl_array*a){(void)d;(void)t;(void)a;if(w>0)app_w=w;if(h>0)app_h=h;}
static void top_close(void*d,struct xdg_toplevel*t){(void)d;(void)t;exit(0);}
static const struct xdg_toplevel_listener top_listener={.configure=top_configure,.close=top_close};
static void app_configure(void*d,struct xdg_surface*s,uint32_t serial){
    (void)d;xdg_surface_ack_configure(s,serial);
    wl_surface_attach(app_surface,buffer(app_w,app_h,0,0,1),0,0);
    wl_surface_damage(app_surface,0,0,app_w,app_h);
    wl_surface_commit(app_surface);
    printf("APP %d %d\n",app_w,app_h);fflush(stdout);
}
static const struct xdg_surface_listener app_listener={app_configure};
static void global(void*d,struct wl_registry*r,uint32_t id,const char*name,uint32_t v){
    (void)d;
    if(!strcmp(name,"wl_compositor"))compositor=wl_registry_bind(r,id,&wl_compositor_interface,v<5?v:5);
    else if(!strcmp(name,"wl_subcompositor"))subcompositor=wl_registry_bind(r,id,&wl_subcompositor_interface,1);
    else if(!strcmp(name,"wl_shm"))shm=wl_registry_bind(r,id,&wl_shm_interface,1);
    else if(!strcmp(name,"wl_seat") && !seat)seat=wl_registry_bind(r,id,&wl_seat_interface,1);
    else if(!strcmp(name,"xdg_wm_base"))wm=wl_registry_bind(r,id,&xdg_wm_base_interface,1);
    else if(!strcmp(name,"zwp_text_input_manager_v3"))tm=wl_registry_bind(r,id,&zwp_text_input_manager_v3_interface,1);
    else if(!strcmp(name,"zwp_input_method_manager_v2"))im_mgr=wl_registry_bind(r,id,&zwp_input_method_manager_v2_interface,1);
}
static void removed(void*d,struct wl_registry*r,uint32_t id){(void)d;(void)r;(void)id;}
static const struct wl_registry_listener registry_listener={global,removed};
int main(void){
    display=wl_display_connect(NULL);assert(display);
    struct wl_registry *registry=wl_display_get_registry(display);
    wl_registry_add_listener(registry,&registry_listener,NULL);
    wl_display_roundtrip(display);
    assert(compositor && shm && seat && wm && tm && im_mgr);
    xdg_wm_base_add_listener(wm,&wm_listener,NULL);
    im=zwp_input_method_manager_v2_get_input_method(im_mgr,seat);
    zwp_input_method_v2_add_listener(im,&im_listener,NULL);
    ti=zwp_text_input_manager_v3_get_text_input(tm,seat);
    zwp_text_input_v3_add_listener(ti,&ti_listener,NULL);
    app_surface=wl_compositor_create_surface(compositor);
    struct xdg_surface *xs=xdg_wm_base_get_xdg_surface(wm,app_surface);
    xdg_surface_add_listener(xs,&app_listener,NULL);
    struct xdg_toplevel *top=xdg_surface_get_toplevel(xs);
    xdg_toplevel_add_listener(top,&top_listener,NULL);
    xdg_toplevel_set_app_id(top,"popup-canvas-probe");
    xdg_toplevel_set_title(top,"Isolated popup canvas test");
    wl_surface_commit(app_surface);
    popup_surface=wl_compositor_create_surface(compositor);
    popup=zwp_input_method_v2_get_input_popup_surface(im,popup_surface);
    zwp_input_popup_surface_v2_add_listener(popup,&popup_listener,NULL);
    wl_display_roundtrip(display);
    puts("READY");fflush(stdout);
    struct pollfd fds[2]={{wl_display_get_fd(display),POLLIN,0},{STDIN_FILENO,POLLIN,0}};
    while(1){
        wl_display_dispatch_pending(display);wl_display_flush(display);
        if(poll(fds,2,-1)<0)break;
        if(fds[0].revents&POLLIN)if(wl_display_dispatch(display)<0)break;
        if(fds[1].revents&POLLIN){
            char line[128];int a,b,c,e,f,g;
            if(!fgets(line,sizeof(line),stdin))break;
            if(sscanf(line,"rect %d %d %d",&a,&b,&c)==3){rx=a;ry=b;rh=c;rect();wl_display_roundtrip(display);puts("MOVED");fflush(stdout);}
            else if(sscanf(line,"draw %d %d %d %d",&a,&b,&c,&e)==4)draw(a,b,c,e);
            else if(sscanf(line,"offset %d %d",&a,&b)==2){wl_surface_offset(popup_surface,a,b);wl_surface_commit(popup_surface);wl_display_roundtrip(display);puts("OFFSET");fflush(stdout);}
            else if(sscanf(line,"child %d %d %d %d %d %d",&a,&b,&c,&e,&f,&g)==6)child(a,b,c,e,f,g);
            else if(!strncmp(line,"quit",4))break;
        }
    }
    zwp_text_input_v3_disable(ti);
    zwp_text_input_v3_commit(ti);
    wl_display_roundtrip(display);
    zwp_input_popup_surface_v2_destroy(popup);
    if(child_role)wl_subsurface_destroy(child_role);
    if(child_surface)wl_surface_destroy(child_surface);
    wl_surface_destroy(popup_surface);
    zwp_input_method_v2_destroy(im);
    wl_display_roundtrip(display);
    wl_display_disconnect(display);return 0;
}
