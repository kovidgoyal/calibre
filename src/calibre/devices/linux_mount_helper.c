#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include <string.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <fcntl.h>

#define MARKER ".created_by_calibre_mount_helper"

int exists(char *path) {
    struct stat file_info;
    if (stat(path, &file_info) == 0) return 1;
    return 0;
}

int get_root() {
    int res;
    res = setreuid(0, 0);
    if (res != 0) return 1;
    if (setregid(0, 0) != 0) return 1;
    return 0;
}

int do_mount(char *dev, char *mp) {
    char options[1000];
    char marker[2000];
    int errsv;
    if (exists(dev) == 0) {
        fprintf(stderr, "Specified device node does not exist\n");
        return EXIT_FAILURE;
    }
    if (exists(mp) == 0) {
        if (mkdir(mp, S_IRUSR|S_IWUSR|S_IXUSR|S_IRGRP|S_IXGRP|S_IROTH|S_IXOTH) != 0) {
            int errsv = errno;
            fprintf(stderr, "Failed to create mount point with error: %s\n", strerror(errsv));
        }
    }
    strncat(marker, mp, strlen(mp));
    strncat(marker, "/", 1);
    strncat(marker, MARKER, strlen(MARKER));
    if (exists(marker) == 0) {
        int fd = creat(marker, S_IRUSR|S_IWUSR);
        if (fd == -1) {
            int errsv = errno;
            fprintf(stderr, "Failed to create marker with error: %s\n", strerror(errsv));
            return EXIT_FAILURE;
        }
        close(fd);
    }
    snprintf(options, 1000, "rw,noexec,nosuid,sync,nodev,quiet,shortname=mixed,uid=%d,gid=%d,umask=077,fmask=0177,dmask=0077,utf8,iocharset=iso8859-1", getuid(), getgid());
    if (get_root() != 0) {
        fprintf(stderr, "Failed to elevate to root privileges\n");
        return EXIT_FAILURE;
    }
    execlp("mount", "mount", "-t", "vfat", "-o", options, dev, mp, NULL);
    errsv = errno;
    fprintf(stderr, "Failed to mount with error: %s\n", strerror(errsv));
    return EXIT_FAILURE;
}

int do_eject(char *dev, char*mp) {
    char marker[2000];
    int status = EXIT_FAILURE, ret, pid, errsv, i, rmd;
    if (get_root() != 0) {
        fprintf(stderr, "Failed to elevate to root privileges\n");
        return EXIT_FAILURE;
    }
    pid = fork();
    if (pid == -1) {
        fprintf(stderr, "Failed to fork\n");
        return EXIT_FAILURE;
    }
    if (pid == 0) {
        if (get_root() != 0) {
            fprintf(stderr, "Failed to elevate to root privileges\n");
            return EXIT_FAILURE;
        }
        execlp("eject", "eject", "-s", dev, NULL);
        errsv = errno;
        fprintf(stderr, "Failed to eject with error: %s\n", strerror(errsv));
        return EXIT_FAILURE;
    } else {
        for (i =0; i < 7; i++) {
            sleep(1);
            ret = waitpid(pid, &status, WNOHANG);
            if (ret == -1) return EXIT_FAILURE;
            if (ret > 0) break;
        }
        if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {
            strncat(marker, mp, strlen(mp));
            strncat(marker, "/", 1);
            strncat(marker, MARKER, strlen(MARKER));
            if (exists(marker)) {
                int urt = unlink(marker);
                if (urt == -1) {
                    fprintf(stderr, "Failed to unlink marker: %s\n", strerror(errno));
                    return EXIT_FAILURE;
                }
                rmd = rmdir(mp);
                if (rmd == -1) {
                    fprintf(stderr, "Failed to remove mount point: %s\n", strerror(errno));
                    return EXIT_FAILURE;
                }
            }
        }
    }
    return EXIT_SUCCESS;
}

int main(int argc, char** argv)
{
    char *action, *dev, *mp;

    /*printf("Real UID\t= %d\n", getuid());
    printf("Effective UID\t= %d\n", geteuid());
    printf("Real GID\t= %d\n", getgid());
    printf("Effective GID\t= %d\n", getegid());*/

    if (argc != 4) {
        fprintf(stderr, "Needs 3 arguments: action, device node and mount point\n");
        return EXIT_FAILURE;
    }
    action = argv[1]; dev = argv[2]; mp = argv[3];

    if (strncmp(action, "mount", 5) == 0) {
        return do_mount(dev, mp);
    } 
    else if (strncmp(action, "eject", 7) == 0) {
        return do_eject(dev, mp);
    } else {
        fprintf(stderr, "Unrecognized action: must be mount or eject\n");
        return EXIT_FAILURE;
    }

 
    return EXIT_SUCCESS;
}

